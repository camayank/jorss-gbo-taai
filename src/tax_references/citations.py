"""Tax law citation database and utilities."""

from typing import Optional

# Top 20 tax topics with IRC citations
TAX_CITATIONS = {
    "standard_deduction": {
        "irc": "IRC Section 63(c)",
        "form": "Form 1040",
        "pub": "IRS Publication 501",
    },
    "mortgage_interest": {
        "irc": "IRC Section 163(h)",
        "form": "Schedule A (Form 1040)",
        "pub": "IRS Publication 936",
    },
    "child_tax_credit": {
        "irc": "IRC Section 24",
        "form": "Schedule 8812",
        "pub": "IRS Publication 972",
    },
    "earned_income_credit": {
        "irc": "IRC Section 32",
        "form": "Schedule EIC",
        "pub": "IRS Publication 596",
    },
    "salt_deduction": {
        "irc": "IRC Section 164",
        "form": "Schedule A (Form 1040)",
        "pub": "IRS Publication 17",
    },
    "charitable_contributions": {
        "irc": "IRC Section 170",
        "form": "Schedule A (Form 1040)",
        "pub": "IRS Publication 526",
    },
    "medical_expenses": {
        "irc": "IRC Section 213",
        "form": "Schedule A (Form 1040)",
        "pub": "IRS Publication 502",
    },
    "ira_contributions": {
        "irc": "IRC Section 219",
        "form": "Form 1040",
        "pub": "IRS Publication 590-A",
    },
    "401k_contributions": {
        "irc": "IRC Section 401(k)",
        "form": "Form W-2",
        "pub": "IRS Publication 560",
    },
    "hsa_contributions": {
        "irc": "IRC Section 223",
        "form": "Form 8889",
        "pub": "IRS Publication 969",
    },
    "capital_gains": {
        "irc": "IRC Section 1(h)",
        "form": "Schedule D (Form 1040)",
        "pub": "IRS Publication 550",
    },
    "qbi_deduction": {
        "irc": "IRC Section 199A",
        "form": "Form 8995",
        "pub": "IRS Publication 535",
    },
    "self_employment_tax": {
        "irc": "IRC Section 1401",
        "form": "Schedule SE",
        "pub": "IRS Publication 334",
    },
    "estimated_tax": {
        "irc": "IRC Section 6654",
        "form": "Form 1040-ES",
        "pub": "IRS Publication 505",
    },
    "filing_status": {
        "irc": "IRC Section 1",
        "form": "Form 1040",
        "pub": "IRS Publication 501",
    },
    "dependents": {
        "irc": "IRC Section 152",
        "form": "Form 1040",
        "pub": "IRS Publication 501",
    },
    "education_credits": {
        "irc": "IRC Section 25A",
        "form": "Form 8863",
        "pub": "IRS Publication 970",
    },
    "student_loan_interest": {
        "irc": "IRC Section 221",
        "form": "Form 1040",
        "pub": "IRS Publication 970",
    },
    "amt": {
        "irc": "IRC Section 55",
        "form": "Form 6251",
        "pub": "IRS Publication 17",
    },
    "social_security_benefits": {
        "irc": "IRC Section 86",
        "form": "Form 1040",
        "pub": "IRS Publication 915",
    },
}

TOP_20_TOPICS = list(TAX_CITATIONS.keys())


def get_citation(topic: str) -> Optional[str]:
    """Get formatted citation for a tax topic."""
    if topic not in TAX_CITATIONS:
        return None
    c = TAX_CITATIONS[topic]
    return f"Per {c['irc']}. See {c['pub']} for details."


def detect_topics(text: str) -> list:
    """Detect tax topics mentioned in text."""
    text_lower = text.lower()
    topic_keywords = {
        "standard_deduction": ["standard deduction"],
        "mortgage_interest": ["mortgage interest", "home loan interest"],
        "child_tax_credit": ["child tax credit", "ctc", "credit for children"],
        "earned_income_credit": ["earned income credit", "eitc", "eic"],
        "salt_deduction": ["state and local tax", "salt", "property tax deduction"],
        "charitable_contributions": ["charitable", "donation", "charity"],
        "medical_expenses": ["medical expense", "healthcare cost"],
        "ira_contributions": ["ira contribution", "traditional ira", "roth ira"],
        "401k_contributions": ["401k", "401(k)", "retirement contribution"],
        "hsa_contributions": ["hsa", "health savings account"],
        "capital_gains": ["capital gain", "stock sale", "investment gain"],
        "qbi_deduction": ["qbi", "qualified business income", "pass-through"],
        "self_employment_tax": ["self-employment tax", "se tax"],
        "estimated_tax": ["estimated tax", "quarterly tax"],
        "filing_status": ["filing status", "married filing", "head of household"],
        "dependents": ["dependent", "qualifying child", "qualifying relative"],
        "education_credits": ["education credit", "american opportunity", "lifetime learning"],
        "student_loan_interest": ["student loan interest"],
        "amt": ["alternative minimum tax", "amt"],
        "social_security_benefits": ["social security benefit", "ss benefit"],
    }

    detected = []
    for topic, keywords in topic_keywords.items():
        if any(kw in text_lower for kw in keywords):
            detected.append(topic)
    return detected


def add_citations_to_response(response: str) -> str:
    """Add relevant tax law citations to a response."""
    topics = detect_topics(response)
    if not topics:
        return response

    citations = []
    for topic in topics[:3]:  # Limit to 3 citations
        citation = get_citation(topic)
        if citation:
            citations.append(citation)

    if citations:
        citation_text = "\n\n**Tax Law References:**\n" + "\n".join(f"- {c}" for c in citations)
        return response + citation_text
    return response
