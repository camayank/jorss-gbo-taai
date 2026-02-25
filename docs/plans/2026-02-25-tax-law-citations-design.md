# Tax Law Citations (MVP) Design Document

**Date:** 2026-02-25
**Status:** Approved
**Approach:** Top 20 Citation Mapping (MVP)

## Overview

Add tax law citations to AI responses so users can verify advice and CPAs can audit logic. MVP focuses on the top 20 most-used tax rules.

## Problem

The SWOT analysis identified "AI Responses Lack Tax Law Citations" as a Risk 9/10 issue:
- AI gives advice with ZERO references to IRC sections, IRS publications, or forms
- Users can't verify advice
- CPAs can't audit logic
- Advice is undefendable in IRS audit

Current: "You can deduct mortgage interest"
Should Be: "Per IRC Section 163(h), qualified residence interest is deductible. See IRS Pub 936."

## MVP Design

### Citation Database

**File: `src/tax_references/citations.py`**

```python
TAX_CITATIONS = {
    "mortgage_interest": {
        "irc": "IRC Section 163(h)",
        "form": "Schedule A (Form 1040)",
        "pub": "IRS Publication 936",
        "summary": "Qualified residence interest deduction"
    },
    "standard_deduction": {
        "irc": "IRC Section 63(c)",
        "form": "Form 1040",
        "pub": "IRS Publication 501",
        "summary": "Standard deduction amounts"
    },
    "child_tax_credit": {
        "irc": "IRC Section 24",
        "form": "Schedule 8812",
        "pub": "IRS Publication 972",
        "summary": "Child Tax Credit"
    },
    # ... 17 more common citations
}

def get_citation(topic: str) -> Optional[str]:
    """Get formatted citation for a tax topic."""
    if topic in TAX_CITATIONS:
        c = TAX_CITATIONS[topic]
        return f"Per {c['irc']}. See {c['pub']} for details."
    return None
```

### Top 20 Citations to Include

1. Standard Deduction (IRC Section 63(c))
2. Mortgage Interest (IRC Section 163(h))
3. Child Tax Credit (IRC Section 24)
4. Earned Income Credit (IRC Section 32)
5. State/Local Tax Deduction (IRC Section 164)
6. Charitable Contributions (IRC Section 170)
7. Medical Expenses (IRC Section 213)
8. IRA Contributions (IRC Section 219)
9. 401(k) Contributions (IRC Section 401(k))
10. HSA Contributions (IRC Section 223)
11. Capital Gains (IRC Section 1(h))
12. Qualified Business Income (IRC Section 199A)
13. Self-Employment Tax (IRC Section 1401)
14. Estimated Tax Payments (IRC Section 6654)
15. Filing Status (IRC Section 1)
16. Dependents (IRC Section 152)
17. Education Credits (IRC Section 25A)
18. Student Loan Interest (IRC Section 221)
19. AMT (IRC Section 55)
20. Social Security Benefits (IRC Section 86)

### Integration with AI Responses

**File: `src/web/intelligent_advisor_api.py`**

```python
def add_citations_to_response(response: str, topics: list[str]) -> str:
    """Add relevant tax law citations to AI response."""
    citations = []
    for topic in topics:
        citation = get_citation(topic)
        if citation:
            citations.append(citation)

    if citations:
        citation_text = "\n\n**Tax Law References:**\n" + "\n".join(f"- {c}" for c in citations)
        return response + citation_text
    return response

def detect_topics(response: str) -> list[str]:
    """Detect tax topics mentioned in response for citation lookup."""
    # Simple keyword matching for MVP
    topic_keywords = {
        "mortgage_interest": ["mortgage interest", "home loan interest"],
        "standard_deduction": ["standard deduction"],
        "child_tax_credit": ["child tax credit", "ctc"],
        # ... etc
    }
```

### Response Format

Before:
```
Based on your income, you may qualify for the Earned Income Credit,
which could save you up to $7,430.
```

After:
```
Based on your income, you may qualify for the Earned Income Credit,
which could save you up to $7,430.

**Tax Law References:**
- Per IRC Section 32. See IRS Publication 596 for details.
```

## Testing Strategy

```python
class TestTaxLawCitations:
    def test_citation_lookup_returns_formatted_string(self):
        """get_citation returns properly formatted citation."""

    def test_topic_detection_finds_keywords(self):
        """detect_topics identifies tax topics in response text."""

    def test_citations_added_to_calculation_response(self):
        """Calculation responses include relevant citations."""

    def test_unknown_topic_returns_none(self):
        """Unknown topics don't add citations."""
```

## Files Changed

| File | Action | Lines |
|------|--------|-------|
| `src/tax_references/citations.py` | Create | ~120 |
| `src/tax_references/__init__.py` | Create | ~5 |
| `src/web/intelligent_advisor_api.py` | Modify | ~30 |
| `tests/test_tax_citations.py` | Create | ~50 |

**Total: ~205 lines**

## Out of Scope (Future)

- Full IRC section database (5,000+ sections)
- Dynamic citation lookup based on LLM analysis
- Links to IRS.gov pages
- Court case citations
- State tax law references
