"""Message parsing and intent detection for the Intelligent Advisor.

Extracted from intelligent_advisor_api.py for maintainability."""

import re
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "parse_user_message",
    "EnhancedParser",
    "enhanced_parse_user_message",
    "ConversationContext",
    "detect_user_intent",
]


def parse_user_message(message: str, current_profile: dict) -> dict:
    """
    Comprehensive parser for tax-relevant information from natural language.
    Handles all permutations of filing status, income, deductions, credits, etc.
    """
    import re
    msg_lower = message.lower().strip()
    msg_original = message.strip()
    updates = {}

    # =========================================================================
    # 1. FILING STATUS DETECTION (5 types with variations)
    # =========================================================================
    filing_patterns = {
        "single": [
            r"\bsingle\b", r"\bfiling\s*(as\s*)?single\b",
            r"\bi('m|am)\s*(filing\s*)?(as\s*)?single\b",
            r"\bnot\s*married\b", r"\bunmarried\b"
        ],
        "married_joint": [
            r"\bmarried\s*filing\s*joint", r"\bmarried\s*joint", r"\bmfj\b",
            r"\bjointly\b", r"\bmarried\b(?!.*separate)", r"\bwife\b", r"\bhusband\b",
            r"\bspouse\b(?!.*separate)", r"\bwe\s*(file|are)\s*together\b"
        ],
        "married_separate": [
            r"\bmarried\s*filing\s*separate", r"\bmarried\s*separate", r"\bmfs\b",
            r"\bseparately\b", r"\bfile\s*separate", r"\bown\s*return\b"
        ],
        "head_of_household": [
            r"\bhead\s*of\s*household\b", r"\bhoh\b", r"\bhead\s*household\b",
            r"\bsingle\s*(parent|mom|dad)\b", r"\bunmarried\s*with\s*(kid|child|dependent)\b"
        ],
        "qualifying_widow": [
            r"\bqualifying\s*widow", r"\bsurviving\s*spouse\b", r"\bwidow(er)?\b",
            r"\bspouse\s*(died|passed|deceased)\b"
        ]
    }
    for status, patterns in filing_patterns.items():
        for pattern in patterns:
            if re.search(pattern, msg_lower):
                updates["filing_status"] = status
                break
        if "filing_status" in updates:
            break

    # =========================================================================
    # 2. INCOME DETECTION (Multiple types and formats)
    # =========================================================================

    # Direct dollar amounts with various formats
    income_patterns = [
        r'\$\s*([\d,]+(?:\.\d{2})?)\s*(?:k|K|thousand)?',  # $50,000 or $50k
        r'([\d,]+(?:\.\d{2})?)\s*(?:k|K|thousand)\b',  # 50k, 150K
        r'(?:make|earn|income|salary|gross|net|about|around|approximately)\s*(?:is|of|:)?\s*\$?\s*([\d,]+)',
        r'(?:with|have)\s*(?:an?\s*)?income\s*(?:of|:)?\s*\$?\s*([\d,]+)',  # "with income of 75000"
        r'([\d,]+)\s*(?:per\s*year|annually|a\s*year|yearly)',
    ]

    for pattern in income_patterns:
        match = re.search(pattern, msg_original, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                amount = float(amount_str)
                # Handle 'k' suffix
                if re.search(r'\d\s*[kK]\b', msg_original):
                    if amount < 1000:  # 50k means 50,000 not 50000k
                        amount *= 1000
                # Reasonable income range
                if 1000 <= amount <= 100000000:
                    updates["total_income"] = amount
                    break
            except ValueError:
                pass

    # Income range detection
    income_ranges = {
        25000: [r"under\s*\$?50", r"less\s*than\s*\$?50", r"below\s*\$?50"],
        75000: [r"\$?50.*\$?100", r"50\s*to\s*100", r"between\s*50.*100"],
        150000: [r"\$?100.*\$?200", r"100\s*to\s*200", r"between\s*100.*200"],
        350000: [r"\$?200.*\$?500", r"200\s*to\s*500", r"few\s*hundred\s*thousand"],
        750000: [r"\$?500.*\$?1\s*m", r"half\s*million", r"500\s*to.*million"],
        1500000: [r"over\s*(a\s*)?million", r"more\s*than.*million", r"1\s*m\+"],
    }
    if "total_income" not in updates:
        for amount, patterns in income_ranges.items():
            for pattern in patterns:
                if re.search(pattern, msg_lower):
                    updates["total_income"] = amount
                    break

    # =========================================================================
    # 3. INCOME TYPE DETECTION
    # =========================================================================

    # W-2 Employment
    if re.search(r'\bw-?2\b|\bemployee\b|\bsalaried\b|\bwages\b', msg_lower):
        updates["income_type"] = "w2"
        updates["is_self_employed"] = False

    # Self-Employment / Business
    if re.search(r'\bself[- ]?employ|\b1099\b|\bfreelance|\bcontractor|\bgig\b|\buber\b|\blyft\b|\bside\s*(hustle|business|gig)', msg_lower):
        updates["is_self_employed"] = True
        updates["income_type"] = "self_employed"

    # Business income amount
    biz_match = re.search(r'(?:business|self[- ]?employ|1099|freelance)\s*(?:income|earn|make|revenue)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if biz_match:
        try:
            updates["business_income"] = float(biz_match.group(1).replace(',', ''))
        except ValueError:
            updates["_clarification_needed"] = {
                "field": "business_income",
                "message": "I couldn't quite understand that amount. Could you tell me just the number? For example: $75,000"
            }

    # Rental Income
    if re.search(r'\brental|\bland\s*lord|\bproperty\s*income|\btenant', msg_lower):
        updates["has_rental_income"] = True
        rental_match = re.search(r'rental\s*(?:income)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
        if rental_match:
            try:
                updates["rental_income"] = float(rental_match.group(1).replace(',', ''))
            except ValueError:
                updates["_clarification_needed"] = {
                    "field": "rental_income",
                    "message": "I couldn't quite understand that amount. Could you tell me just the number? For example: $24,000"
                }

    # Investment Income
    if re.search(r'\binvestment|\bdividend|\bcapital\s*gain|\bstock|\bcrypto|\btrading', msg_lower):
        updates["has_investment_income"] = True
        inv_match = re.search(r'(?:investment|dividend|capital\s*gain)\s*(?:income)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
        if inv_match:
            try:
                updates["investment_income"] = float(inv_match.group(1).replace(',', ''))
            except ValueError:
                updates["_clarification_needed"] = {
                    "field": "investment_income",
                    "message": "I couldn't quite understand that amount. Could you tell me just the number? For example: $10,000"
                }

    # Retirement Income
    if re.search(r'\bretired|\bpension|\bsocial\s*security|\b401k\s*withdraw|\bira\s*distribut', msg_lower):
        updates["has_retirement_income"] = True

    # =========================================================================
    # 4. STATE DETECTION (All 50 + DC)
    # =========================================================================
    # Full state names (safe to check without word boundaries)
    full_state_names = {
        "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
        "california": "CA", "cali": "CA", "colorado": "CO", "connecticut": "CT",
        "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI",
        "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
        "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME",
        "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
        "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
        "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
        "new york": "NY", "nyc": "NY", "north carolina": "NC", "north dakota": "ND",
        "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
        "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
        "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
        "virginia": "VA", "washington": "WA", "west virginia": "WV",
        "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC", "washington dc": "DC"
    }
    # Two-letter state abbreviations (need word boundaries)
    state_abbrevs = {
        "al": "AL", "ak": "AK", "az": "AZ", "ar": "AR", "ca": "CA", "co": "CO",
        "ct": "CT", "de": "DE", "fl": "FL", "ga": "GA", "hi": "HI", "id": "ID",
        "il": "IL", "ia": "IA", "ks": "KS", "ky": "KY", "la": "LA",
        "me": "ME", "md": "MD", "ma": "MA", "mi": "MI", "mn": "MN", "ms": "MS",
        "mo": "MO", "mt": "MT", "ne": "NE", "nv": "NV", "nh": "NH", "nj": "NJ",
        "nm": "NM", "ny": "NY", "nc": "NC", "nd": "ND", "oh": "OH", "ok": "OK",
        "pa": "PA", "ri": "RI", "sc": "SC", "sd": "SD", "tn": "TN",
        "tx": "TX", "ut": "UT", "vt": "VT", "va": "VA", "wa": "WA", "wv": "WV",
        "wi": "WI", "wy": "WY", "dc": "DC", "d.c.": "DC"
    }
    # Exclude common words that conflict with state abbreviations
    # (in, or, me, ok, hi, la, ma, pa, oh, co, de, id, ne, md, al, ar, ak)
    # Check longer names first to avoid partial matches
    for state_name in sorted(full_state_names.keys(), key=len, reverse=True):
        if state_name in msg_lower:
            updates["state"] = full_state_names[state_name]
            break
    # If no full name found, check abbreviations with word boundaries
    if "state" not in updates:
        for abbrev, code in state_abbrevs.items():
            # Use word boundaries to avoid matching inside words
            # Also require context like "in", "from", "live", "state" nearby
            pattern = rf'\b{re.escape(abbrev)}\b'
            if re.search(pattern, msg_lower):
                # Additional check: must have location context or be standalone
                context_pattern = rf'(?:in|from|live|state|resident|living)\s+{re.escape(abbrev)}\b|\b{re.escape(abbrev)}\s+(?:state|resident)'
                if re.search(context_pattern, msg_lower) or re.search(rf'^{re.escape(abbrev)}$', msg_lower.strip()):
                    updates["state"] = code
                    break

    # =========================================================================
    # 5. DEPENDENTS DETECTION
    # =========================================================================
    word_to_num = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                   "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

    # Numeric patterns
    dep_match = re.search(r'(\d+)\s*(?:dependent|child|kid|children|minor)', msg_lower)
    if dep_match:
        updates["dependents"] = min(int(dep_match.group(1)), 20)  # Cap at 20
    else:
        # Word patterns
        for word, num in word_to_num.items():
            if re.search(rf'\b{word}\s*(?:dependent|child|kid|children)', msg_lower):
                updates["dependents"] = num
                break

    # No dependents
    if re.search(r'\bno\s*(?:dependent|child|kid)|don\'t\s*have\s*(?:any\s*)?(?:kid|child|dependent)|childless', msg_lower):
        updates["dependents"] = 0

    # =========================================================================
    # 6. DEDUCTION DETECTION
    # =========================================================================

    # Mortgage interest
    mort_match = re.search(r'mortgage\s*(?:interest)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if mort_match:
        try:
            updates["mortgage_interest"] = float(mort_match.group(1).replace(',', ''))
        except ValueError:
            updates["_clarification_needed"] = {
                "field": "mortgage_interest",
                "message": "I couldn't quite understand that amount. Could you tell me just the number? For example: $12,000"
            }
    elif re.search(r'\bmortgage\b|\bhome\s*loan\b|\bhomeowner\b', msg_lower):
        updates["has_mortgage"] = True

    # Property tax
    prop_match = re.search(r'property\s*tax\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if prop_match:
        try:
            updates["property_taxes"] = float(prop_match.group(1).replace(',', ''))
        except ValueError:
            updates["_clarification_needed"] = {
                "field": "property_taxes",
                "message": "I couldn't quite understand that amount. Could you tell me just the number? For example: $5,000"
            }

    # Charitable donations
    char_match = re.search(r'(?:donat|charit|contribut)\w*\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if char_match:
        try:
            updates["charitable_donations"] = float(char_match.group(1).replace(',', ''))
        except ValueError:
            updates["_clarification_needed"] = {
                "field": "charitable_donations",
                "message": "I couldn't quite understand that amount. Could you tell me just the number? For example: $5,000"
            }
    elif re.search(r'\bdonat|\bcharit|\bcontribut|\btithe|\bgive\s*to\s*church', msg_lower):
        updates["has_charitable"] = True

    # Medical expenses
    med_match = re.search(r'medical\s*(?:expense)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if med_match:
        try:
            updates["medical_expenses"] = float(med_match.group(1).replace(',', ''))
        except ValueError:
            updates["_clarification_needed"] = {
                "field": "medical_expenses",
                "message": "I couldn't quite understand that amount. Could you tell me just the number? For example: $8,000"
            }

    # Student loan interest
    student_match = re.search(r'student\s*loan\s*(?:interest)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if student_match:
        try:
            updates["student_loan_interest"] = min(float(student_match.group(1).replace(',', '')), 2500)
        except ValueError:
            updates["_clarification_needed"] = {
                "field": "student_loan_interest",
                "message": "I couldn't quite understand that amount. Could you tell me just the number? For example: $2,000"
            }
    elif re.search(r'\bstudent\s*loan\b', msg_lower):
        updates["has_student_loans"] = True

    # =========================================================================
    # 7. RETIREMENT CONTRIBUTIONS
    # =========================================================================

    # 401k
    k401_match = re.search(r'401\s*k?\s*(?:contribut)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if k401_match:
        try:
            updates["retirement_401k"] = min(float(k401_match.group(1).replace(',', '')), 30500)
        except ValueError:
            updates["_clarification_needed"] = {
                "field": "retirement_401k",
                "message": "I couldn't quite understand that amount. Could you tell me just the number? For example: $20,000"
            }
    elif re.search(r'\b401\s*k\b', msg_lower):
        updates["has_401k"] = True

    # IRA
    ira_match = re.search(r'(?:traditional\s*)?ira\s*(?:contribut)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if ira_match:
        try:
            updates["retirement_ira"] = min(float(ira_match.group(1).replace(',', '')), 8000)
        except ValueError:
            updates["_clarification_needed"] = {
                "field": "retirement_ira",
                "message": "I couldn't quite understand that amount. Could you tell me just the number? For example: $6,500"
            }

    # HSA
    hsa_match = re.search(r'hsa\s*(?:contribut)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if hsa_match:
        try:
            updates["hsa_contributions"] = min(float(hsa_match.group(1).replace(',', '')), 8550)
        except ValueError:
            updates["_clarification_needed"] = {
                "field": "hsa_contributions",
                "message": "I couldn't quite understand that amount. Could you tell me just the number? For example: $3,850"
            }
    elif re.search(r'\bhsa\b|\bhealth\s*savings\b', msg_lower):
        updates["has_hsa"] = True

    # =========================================================================
    # 8. LIFE EVENTS
    # =========================================================================

    if re.search(r'\bgot\s*married|\bjust\s*married|\bnewlywed|\bwedding\s*this\s*year', msg_lower):
        updates["life_event"] = "married"
    elif re.search(r'\bdivorc|\bseparat|\bsplit\s*up', msg_lower):
        updates["life_event"] = "divorced"
    elif re.search(r'\bnew\s*baby|\bhad\s*a\s*(baby|child)|\bbaby\s*born|\bnewborn', msg_lower):
        updates["life_event"] = "new_baby"
        if "dependents" not in updates:
            updates["dependents"] = current_profile.get("dependents", 0) + 1
    elif re.search(r'\bbought\s*a?\s*house|\bhome\s*purchase|\bnew\s*home\s*owner|\bfirst\s*time\s*buyer', msg_lower):
        updates["life_event"] = "home_purchase"
        updates["has_mortgage"] = True
    elif re.search(r'\bsold\s*(my\s*)?(house|home)|\bhome\s*sale', msg_lower):
        updates["life_event"] = "home_sale"
    elif re.search(r'\bretir|\bstopped\s*working|\bleft\s*(my\s*)?job.*retire', msg_lower):
        updates["life_event"] = "retired"
    elif re.search(r'\bnew\s*job|\bchanged\s*job|\bswitch.*employ|\bstart.*new\s*position', msg_lower):
        updates["life_event"] = "job_change"
    elif re.search(r'\blost\s*(my\s*)?job|\bunemploy|\blaid\s*off|\bfired', msg_lower):
        updates["life_event"] = "job_loss"
        updates["has_unemployment"] = True

    # =========================================================================
    # 9. YES/NO RESPONSE HANDLING
    # =========================================================================

    yes_patterns = [r'\byes\b', r'\byeah\b', r'\byep\b', r'\bsure\b', r'\bcorrect\b',
                    r'\bthat\'s\s*right\b', r'\baffirmative\b', r'\bi\s*do\b', r'\bi\s*have\b']
    no_patterns = [r'\bno\b', r'\bnope\b', r'\bnah\b', r'\bnegative\b', r'\bi\s*don\'t\b',
                   r'\bi\s*do\s*not\b', r'\bnone\b', r'\bnothing\b']

    is_yes = any(re.search(p, msg_lower) for p in yes_patterns)
    is_no = any(re.search(p, msg_lower) for p in no_patterns)

    if is_yes or is_no:
        updates["_response_type"] = "yes" if is_yes else "no"

    # =========================================================================
    # 10. AGE DETECTION
    # =========================================================================

    age_match = re.search(r'(?:i\'m|i\s*am|age)\s*(\d{1,3})\s*(?:years?\s*old)?', msg_lower)
    if age_match:
        age = int(age_match.group(1))
        if 0 <= age <= 120:
            updates["age"] = age

    # Over 65 check
    if re.search(r'\bsenior\b|\bover\s*65\b|\bretire[ed]|\belderly\b', msg_lower):
        updates["age"] = max(current_profile.get("age", 65), 65)

    # =========================================================================
    # 11. CORRECTION DETECTION - Detect when user is changing previous answers
    # =========================================================================

    correction_patterns = [
        r'\bactually\b', r'\bi\s*meant\b', r'\bcorrection\b', r'\bsorry\b.*\bwrong\b',
        r'\blet\s*me\s*correct\b', r'\bthat\s*was\s*wrong\b', r'\bi\s*made\s*a\s*mistake\b',
        r'\bchange\s*(that|my|it)\b', r'\bnot\s*\w+\s*but\b', r'\bwait\b.*\bactually\b',
        r'\bundo\b', r'\bgo\s*back\b', r'\bstart\s*over\b', r'\breset\b',
        r'\binstead\s*of\b', r'\brather\b.*\bthan\b'
    ]

    is_correction = any(re.search(p, msg_lower) for p in correction_patterns)
    if is_correction:
        updates["_is_correction"] = True

    # Detect explicit contradictions with current profile
    if current_profile.get("filing_status") and "filing_status" in updates:
        if current_profile["filing_status"] != updates["filing_status"]:
            updates["_is_correction"] = True
            updates["_changed_field"] = "filing_status"

    if current_profile.get("total_income") and "total_income" in updates:
        # If income changed by more than 20%, likely a correction
        old_income = current_profile["total_income"]
        new_income = updates["total_income"]
        if abs(new_income - old_income) / max(old_income, 1) > 0.2:
            updates["_is_correction"] = True
            updates["_changed_field"] = "total_income"

    return updates


# =============================================================================
# ENHANCED PARSING SYSTEM - Robustness Layer
# =============================================================================
# This module adds:
# 1. Confidence scoring for extracted values
# 2. Fuzzy matching for typos
# 3. Word-to-number conversion
# 4. Validation with helpful feedback
# 5. Conflict detection
# 6. Field-specific undo
# 7. Contextual follow-ups
# =============================================================================

class EnhancedParser:
    """
    Enhanced parsing layer that wraps parse_user_message with robustness features.
    """

    # Fuzzy matching dictionaries for common typos
    FILING_STATUS_FUZZY = {
        # Single variations
        "singl": "single", "singel": "single", "singe": "single", "sngle": "single",
        "unmaried": "single", "unmmaried": "single", "not maried": "single",
        # Married joint variations
        "maried": "married_joint", "marred": "married_joint", "marriedjoint": "married_joint",
        "mfj": "married_joint", "jointly": "married_joint", "joint": "married_joint",
        "maried jointly": "married_joint", "married jointley": "married_joint",
        # Married separate variations
        "mfs": "married_separate", "seperately": "married_separate", "seperate": "married_separate",
        "married seperately": "married_separate", "maried seperate": "married_separate",
        # Head of household variations
        "hoh": "head_of_household", "headofhousehold": "head_of_household",
        "head of houshold": "head_of_household", "head of householde": "head_of_household",
        "head of the household": "head_of_household", "household head": "head_of_household",
        # Qualifying widow variations
        "widow": "qualifying_widow", "widower": "qualifying_widow",
        "surviving spouse": "qualifying_widow", "qw": "qualifying_widow",
    }

    STATE_FUZZY = {
        # Common misspellings
        "califronia": "CA", "californai": "CA", "calfornia": "CA", "cali": "CA",
        "newyork": "NY", "new yourk": "NY", "neew york": "NY",
        "texs": "TX", "texaz": "TX", "teaxs": "TX",
        "florda": "FL", "flordia": "FL", "fla": "FL",
        "illinos": "IL", "illinoise": "IL", "ilinois": "IL",
        "pensylvania": "PA", "pennsilvania": "PA", "penn": "PA",
        "massachusets": "MA", "massachussetts": "MA", "mass": "MA",
        "conneticut": "CT", "conecticut": "CT", "conn": "CT",
        "washingon": "WA", "wahsington": "WA",
        "arizonia": "AZ", "arizone": "AZ",
        "colrado": "CO", "colorodo": "CO",
        "michgan": "MI", "michagan": "MI",
        "minnestoa": "MN", "minesota": "MN",
        "georiga": "GA", "goergia": "GA",
        "virgina": "VA", "virgnia": "VA",
        "north carolna": "NC", "north carlina": "NC",
        "south carolna": "SC", "south carlina": "SC",
    }

    # Word-to-number mappings
    WORD_NUMBERS = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
        "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
        "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
        "hundred": 100, "thousand": 1000, "million": 1000000, "billion": 1000000000,
        "k": 1000, "m": 1000000, "mil": 1000000,
    }

    # Confidence thresholds
    HIGH_CONFIDENCE = 0.9
    MEDIUM_CONFIDENCE = 0.7
    LOW_CONFIDENCE = 0.5
    CONFIRMATION_THRESHOLD = 0.75  # Ask for confirmation below this

    @classmethod
    def words_to_number(cls, text: str) -> tuple:
        """
        Convert word-based numbers to numeric values.

        Examples:
            "one hundred fifty thousand" -> (150000, 0.95)
            "seventy five K" -> (75000, 0.9)
            "two point five million" -> (2500000, 0.9)

        Returns:
            (number, confidence) or (None, 0) if no number found
        """
        import re
        text_lower = text.lower().strip()

        # Handle "X point Y" patterns (e.g., "two point five million")
        point_match = re.search(
            r'(\w+)\s+point\s+(\w+)\s*(hundred|thousand|k|million|m|mil|billion)?',
            text_lower
        )
        if point_match:
            whole = cls.WORD_NUMBERS.get(point_match.group(1), 0)
            decimal = cls.WORD_NUMBERS.get(point_match.group(2), 0)
            multiplier_word = point_match.group(3) or ""
            multiplier = cls.WORD_NUMBERS.get(multiplier_word, 1)

            if whole > 0 or decimal > 0:
                # Convert decimal part (e.g., "five" -> 0.5)
                decimal_value = decimal / 10 if decimal < 10 else decimal / 100
                result = (whole + decimal_value) * multiplier
                return (result, 0.85)

        # Handle compound word numbers
        # Pattern: [number words] [multiplier]
        # E.g., "one hundred fifty thousand", "seventy five k"

        # First, try to find multiplier
        multiplier = 1
        multiplier_confidence = 1.0
        for word, value in [("billion", 1e9), ("million", 1e6), ("mil", 1e6), ("m", 1e6),
                            ("thousand", 1e3), ("k", 1e3)]:
            if re.search(rf'\b{word}\b', text_lower):
                multiplier = value
                # Remove multiplier from text for further processing
                text_lower = re.sub(rf'\b{word}\b', '', text_lower)
                break

        # Parse remaining number words
        words = text_lower.split()
        number = 0
        current = 0
        found_number = False

        for word in words:
            word = word.strip(',$.')
            if word in cls.WORD_NUMBERS:
                found_number = True
                val = cls.WORD_NUMBERS[word]
                if val == 100:
                    current = (current if current else 1) * 100
                elif val >= 1000:
                    current = (current if current else 1) * val
                    number += current
                    current = 0
                else:
                    current += val
            elif word.isdigit():
                found_number = True
                current += int(word)

        number += current

        if found_number and number > 0:
            result = number * multiplier
            # Confidence based on complexity of parsing
            confidence = 0.9 if multiplier == 1 else 0.85
            return (result, confidence)

        return (None, 0)

    @classmethod
    def fuzzy_match_filing_status(cls, text: str) -> tuple:
        """
        Fuzzy match filing status with confidence score.

        Returns:
            (filing_status, confidence) or (None, 0)
        """
        import re
        text_lower = text.lower().strip()

        # First try exact matches (high confidence)
        exact_patterns = {
            "single": (r'\bsingle\b', 0.95),
            "married_joint": (r'\bmarried\s*filing\s*joint', 0.98),
            "married_separate": (r'\bmarried\s*filing\s*separate', 0.98),
            "head_of_household": (r'\bhead\s*of\s*household\b', 0.98),
            "qualifying_widow": (r'\bqualifying\s*widow', 0.95),
        }

        for status, (pattern, confidence) in exact_patterns.items():
            if re.search(pattern, text_lower):
                return (status, confidence)

        # Try fuzzy matches (lower confidence)
        for typo, correct_status in cls.FILING_STATUS_FUZZY.items():
            if typo in text_lower:
                return (correct_status, 0.75)  # Lower confidence for fuzzy

        return (None, 0)

    @classmethod
    def fuzzy_match_state(cls, text: str) -> tuple:
        """
        Fuzzy match state with confidence score.

        Returns:
            (state_code, confidence) or (None, 0)
        """
        text_lower = text.lower().strip()

        # Check fuzzy matches first
        for typo, correct_state in cls.STATE_FUZZY.items():
            if typo in text_lower:
                return (correct_state, 0.80)  # Medium confidence for typo correction

        return (None, 0)

    @classmethod
    def detect_ambiguous_amounts(cls, text: str) -> list:
        """
        Detect potentially ambiguous amounts that need confirmation.

        Returns list of (amount, interpretation, confidence) tuples
        """
        import re
        ambiguous = []
        text_lower = text.lower()

        # Pattern: bare number without context (e.g., "150" could be $150 or $150,000)
        bare_number = re.search(r'\b(\d{2,3})\b(?!\s*[kK%])', text)
        if bare_number:
            num = int(bare_number.group(1))
            if 50 <= num <= 999:  # Ambiguous range
                ambiguous.append({
                    "value": num,
                    "interpretations": [
                        {"amount": num, "meaning": f"${num:,}"},
                        {"amount": num * 1000, "meaning": f"${num * 1000:,}"}
                    ],
                    "context": "bare_number",
                    "confidence": 0.5
                })

        # Hedging words reduce confidence
        hedging = ["about", "around", "approximately", "roughly", "maybe", "probably",
                   "i think", "not sure", "something like", "somewhere around"]
        for hedge in hedging:
            if hedge in text_lower:
                ambiguous.append({
                    "type": "hedging_detected",
                    "word": hedge,
                    "confidence_reduction": 0.15
                })
                break

        return ambiguous

    @classmethod
    def validate_extracted_data(cls, extracted: dict, current_profile: dict) -> dict:
        """
        Validate extracted data and return warnings/suggestions.

        Returns:
            {
                "valid": bool,
                "warnings": [...],
                "suggestions": [...],
                "auto_corrections": {...}
            }
        """
        result = {
            "valid": True,
            "warnings": [],
            "suggestions": [],
            "auto_corrections": {}
        }

        # Validate income
        income = extracted.get("total_income")
        if income is not None:
            if income < 0:
                result["warnings"].append({
                    "field": "total_income",
                    "message": "Income cannot be negative.",
                    "suggestion": "Please enter a positive income amount."
                })
                result["auto_corrections"]["total_income"] = abs(income)  # Auto-correct to positive
                result["valid"] = False
            elif income < 100:
                result["warnings"].append({
                    "field": "total_income",
                    "message": f"${income:,.0f} seems very low for annual income.",
                    "suggestion": f"Did you mean ${income * 1000:,.0f}?",
                    "possible_correction": income * 1000
                })
                result["valid"] = False
            elif income > 50000000:
                result["warnings"].append({
                    "field": "total_income",
                    "message": f"${income:,.0f} is unusually high.",
                    "suggestion": "Please confirm this is correct."
                })

        # Validate dependents
        dependents = extracted.get("dependents")
        if dependents is not None:
            if dependents > 10:
                result["warnings"].append({
                    "field": "dependents",
                    "message": f"{dependents} dependents is unusual.",
                    "suggestion": "Please confirm the number of dependents."
                })
            elif dependents < 0:
                result["auto_corrections"]["dependents"] = 0
                result["warnings"].append({
                    "field": "dependents",
                    "message": "Dependents cannot be negative. Set to 0.",
                })

        # Check for conflicts with current profile
        if current_profile.get("filing_status") == "single" and extracted.get("dependents", 0) > 0:
            if not extracted.get("filing_status"):
                result["suggestions"].append({
                    "message": "You're filing as Single but have dependents. Would Head of Household be more beneficial?",
                    "action": "consider_hoh"
                })

        # Validate deduction/credit amounts: $0 to $1,000,000
        deduction_fields = [
            ("mortgage_interest", "mortgage interest"),
            ("property_taxes", "property taxes"),
            ("charitable_donations", "charitable donations"),
            ("medical_expenses", "medical expenses"),
            ("student_loan_interest", "student loan interest"),
        ]
        for field_key, field_label in deduction_fields:
            val = extracted.get(field_key)
            if val is not None:
                if val < 0:
                    result["auto_corrections"][field_key] = abs(val)
                    result["warnings"].append({
                        "field": field_key,
                        "message": f"{field_label.title()} cannot be negative. Corrected to ${abs(val):,.0f}.",
                        "auto_corrected": True
                    })
                elif val > 1000000:
                    result["warnings"].append({
                        "field": field_key,
                        "message": f"${val:,.0f} for {field_label} seems unusually high.",
                        "suggestion": f"Please confirm your {field_label} amount is correct.",
                        "possible_correction": None
                    })
                    result["valid"] = False

        # Validate age: 0 to 120
        age = extracted.get("age")
        if age is not None:
            if age < 0 or age > 120:
                result["warnings"].append({
                    "field": "age",
                    "message": f"Age {age} is outside the valid range (0-120).",
                    "suggestion": "Please provide your correct age."
                })
                result["valid"] = False
            elif age < 16:
                result["warnings"].append({
                    "field": "age",
                    "message": f"Age {age} is unusual for a tax filer.",
                    "suggestion": "Please confirm your age is correct."
                })

        # Validate dependents: 0 to 20
        if dependents is not None and dependents > 20:
            result["auto_corrections"]["dependents"] = 20
            result["warnings"].append({
                "field": "dependents",
                "message": f"{dependents} dependents exceeds the maximum (20). Capped at 20.",
                "auto_corrected": True
            })

        # Check spouse-related conflicts
        if extracted.get("filing_status") == "single":
            spouse_words = ["spouse", "wife", "husband", "married"]
            # This would need the original message - handled in enhanced_parse

        return result

    @classmethod
    def detect_field_specific_undo(cls, message: str) -> dict:
        """
        Detect if user wants to change a specific field.

        Examples:
            "change my income to 90000" -> {"field": "total_income", "new_value": 90000}
            "fix my state to Texas" -> {"field": "state", "new_value": "TX"}
            "my filing status should be single" -> {"field": "filing_status", "new_value": "single"}

        Returns:
            {"field": field_name, "new_value": value} or None
        """
        import re
        msg_lower = message.lower().strip()

        # Helper function to parse income with k/K suffix
        def parse_income_value(text: str) -> float:
            text = text.replace(',', '').strip()
            if text.lower().endswith('k'):
                return float(text[:-1]) * 1000
            return float(text)

        # Patterns for field-specific changes
        # NOTE: These patterns should ONLY match when there's clear correction intent
        # (change, update, fix, correct, actually, meant, sorry, no wait)
        # Regular inputs like "my income is 75" should NOT match here
        field_patterns = [
            # Income changes - explicit correction verbs
            (r'(?:change|update|fix|correct)\s*(?:my\s*)?income\s*(?:to|is|should\s*be)\s*\$?([\d,]+k?)',
             "total_income", lambda m: parse_income_value(m.group(1))),
            # Income - "meant to say" pattern
            (r'(?:i\s*)?meant\s*(?:to\s*say|it\'s)\s*\$?([\d,]+k?)(?:\s*(?:for|as)\s*income)?',
             "total_income", lambda m: parse_income_value(m.group(1))),
            # Income - "actually/sorry/no wait" patterns (correction intent)
            (r'(?:actually|no\s*wait|sorry)\s*(?:it\'?s?|my\s*income\s*is)?\s*\$?([\d,]+k?)(?:\s*(?:for|as)?\s*(?:my\s*)?income)?',
             "total_income", lambda m: parse_income_value(m.group(1))),

            # Filing status changes
            (r'(?:change|update|fix|correct)\s*(?:my\s*)?(?:filing\s*)?status\s*(?:to|is|should\s*be)\s*(\w+)',
             "filing_status", lambda m: cls._normalize_filing_status(m.group(1))),
            (r'(?:i\s*)?(?:am|should\s*be)\s*(?:filing\s*(?:as\s*)?)?(\w+)(?:\s*not\s*\w+)?',
             "filing_status", lambda m: cls._normalize_filing_status(m.group(1))),

            # State changes - standard patterns
            (r'(?:change|update|fix|correct)\s*(?:my\s*)?state\s*(?:to|is|should\s*be)\s*(\w+(?:\s+\w+)?)',
             "state", lambda m: cls._normalize_state(m.group(1))),
            (r'(?:i\s*)?(?:live|moved)\s*(?:in|to)\s*(\w+(?:\s+\w+)?)',
             "state", lambda m: cls._normalize_state(m.group(1))),
            # State - "actually my state is X" pattern
            (r'(?:actually|no\s*wait|sorry)\s*(?:my\s*)?state\s*(?:is|should\s*be)\s*(\w+(?:\s+\w+)?)',
             "state", lambda m: cls._normalize_state(m.group(1))),

            # Dependents changes
            (r'(?:change|update|fix|correct)\s*(?:my\s*)?(?:number\s*of\s*)?dependents?\s*(?:to|is|should\s*be)\s*(\d+)',
             "dependents", lambda m: int(m.group(1))),
            (r'(?:i\s*)?have\s*(\d+)\s*(?:kids?|children|dependents?)',
             "dependents", lambda m: int(m.group(1))),
        ]

        for pattern, field, extractor in field_patterns:
            match = re.search(pattern, msg_lower)
            if match:
                try:
                    value = extractor(match)
                    if value is not None:
                        return {"field": field, "new_value": value, "confidence": 0.85}
                except (ValueError, AttributeError):
                    pass

        return None

    @classmethod
    def _normalize_filing_status(cls, status_text: str) -> str:
        """Normalize filing status text to standard values."""
        status_lower = status_text.lower().strip()
        status_map = {
            "single": "single",
            "married": "married_joint",
            "joint": "married_joint",
            "jointly": "married_joint",
            "separate": "married_separate",
            "separately": "married_separate",
            "hoh": "head_of_household",
            "head": "head_of_household",
            "household": "head_of_household",
            "widow": "qualifying_widow",
            "widower": "qualifying_widow",
        }
        return status_map.get(status_lower)

    @classmethod
    def _normalize_state(cls, state_text: str) -> str:
        """Normalize state text to standard 2-letter code."""
        # Full state name mapping
        state_names = {
            "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
            "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
            "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
            "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
            "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
            "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
            "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
            "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
            "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
            "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
            "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
            "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
            "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
        }

        state_lower = state_text.lower().strip()

        # Check full names first
        if state_lower in state_names:
            return state_names[state_lower]

        # Check if it's already a valid 2-letter code
        if len(state_lower) == 2 and state_lower.upper() in state_names.values():
            return state_lower.upper()

        # Check fuzzy matches
        fuzzy_result, _ = EnhancedParser.fuzzy_match_state(state_text)
        return fuzzy_result

    @classmethod
    def detect_conflicts(cls, message: str, extracted: dict, current_profile: dict) -> list:
        """
        Detect conflicting information in the message or with current profile.

        Returns list of conflict descriptions.
        """
        conflicts = []
        msg_lower = message.lower()

        # Single but mentions spouse
        if extracted.get("filing_status") == "single" or current_profile.get("filing_status") == "single":
            spouse_indicators = ["spouse", "wife", "husband", "we file", "our income", "my partner"]
            for indicator in spouse_indicators:
                if indicator in msg_lower:
                    conflicts.append({
                        "type": "status_spouse_conflict",
                        "message": f"You mentioned '{indicator}' but filing status is Single.",
                        "question": "Are you married? Would Married Filing Jointly be correct?",
                        "options": [
                            {"label": "Yes, I'm married", "value": "married_joint"},
                            {"label": "No, I'm single", "value": "single"}
                        ]
                    })
                    break

        # Head of Household but no dependents mentioned
        if extracted.get("filing_status") == "head_of_household":
            if current_profile.get("dependents") == 0 and not extracted.get("dependents"):
                conflicts.append({
                    "type": "hoh_no_dependents",
                    "message": "Head of Household typically requires a qualifying dependent.",
                    "question": "Do you have dependents living with you?",
                    "options": [
                        {"label": "Yes, I have dependents", "value": "has_dependents"},
                        {"label": "No dependents", "value": "reconsider_status"}
                    ]
                })

        # Income type conflicts
        if extracted.get("is_self_employed") and current_profile.get("income_type") == "w2":
            conflicts.append({
                "type": "income_type_change",
                "message": "You previously indicated W-2 employment but now mention self-employment.",
                "question": "Do you have both W-2 and self-employment income?",
                "options": [
                    {"label": "Yes, both", "value": "mixed_income"},
                    {"label": "Only self-employed now", "value": "self_employed_only"},
                    {"label": "Only W-2", "value": "w2_only"}
                ]
            })

        return conflicts


def enhanced_parse_user_message(message: str, current_profile: dict, session: dict = None) -> dict:
    """
    Enhanced wrapper around parse_user_message that adds:
    - Confidence scoring
    - Fuzzy matching
    - Word-to-number conversion
    - Validation
    - Conflict detection
    - Field-specific undo detection

    Returns:
        {
            "extracted": {...},           # Standard extracted data
            "confidence": {...},          # Confidence scores per field
            "needs_confirmation": [...],  # Fields needing confirmation
            "warnings": [...],            # Validation warnings
            "suggestions": [...],         # Helpful suggestions
            "conflicts": [...],           # Detected conflicts
            "field_update": {...},        # If field-specific update detected
            "ambiguous": [...],           # Ambiguous values detected
        }
    """
    import re

    result = {
        "extracted": {},
        "confidence": {},
        "needs_confirmation": [],
        "warnings": [],
        "suggestions": [],
        "conflicts": [],
        "field_update": None,
        "ambiguous": [],
    }

    msg_lower = message.lower().strip()

    # 0. Check for negative income (special case - standard parser won't catch this)
    neg_income_match = re.search(r'income\s*(?:is|of|:)?\s*-\$?\s*([\d,]+)', msg_lower)
    if neg_income_match:
        neg_value = float(neg_income_match.group(1).replace(',', ''))
        result["extracted"]["total_income"] = neg_value  # Auto-correct to positive
        result["warnings"].append({
            "field": "total_income",
            "message": "Income cannot be negative.",
            "suggestion": f"I've corrected this to ${neg_value:,.0f}."
        })
        result["confidence"]["total_income"] = 0.8
        # Don't return early - continue processing for other fields

    # 1. Check for field-specific update first
    field_update = EnhancedParser.detect_field_specific_undo(message)
    if field_update:
        result["field_update"] = field_update
        result["extracted"][field_update["field"]] = field_update["new_value"]
        result["confidence"][field_update["field"]] = field_update.get("confidence", 0.85)
        return result

    # 2. Try word-to-number conversion for income
    word_num, word_conf = EnhancedParser.words_to_number(message)
    if word_num and word_num >= 1000:  # Likely income
        result["extracted"]["total_income"] = word_num
        result["confidence"]["total_income"] = word_conf
        if word_conf < EnhancedParser.CONFIRMATION_THRESHOLD:
            result["needs_confirmation"].append({
                "field": "total_income",
                "value": word_num,
                "message": f"Just to confirm - is your annual income ${word_num:,.0f}?"
            })

    # 3. Run standard parser
    standard_extracted = parse_user_message(message, current_profile)

    # 4. Check for fuzzy matches on any fields the standard parser missed
    if "filing_status" not in standard_extracted:
        fuzzy_status, status_conf = EnhancedParser.fuzzy_match_filing_status(message)
        if fuzzy_status:
            standard_extracted["filing_status"] = fuzzy_status
            result["confidence"]["filing_status"] = status_conf
            if status_conf < EnhancedParser.CONFIRMATION_THRESHOLD:
                result["needs_confirmation"].append({
                    "field": "filing_status",
                    "value": fuzzy_status,
                    "message": f"I understood your filing status as '{fuzzy_status.replace('_', ' ').title()}'. Is that correct?"
                })

    if "state" not in standard_extracted:
        fuzzy_state, state_conf = EnhancedParser.fuzzy_match_state(message)
        if fuzzy_state:
            standard_extracted["state"] = fuzzy_state
            result["confidence"]["state"] = state_conf

    # 5. Merge with word-to-number results (standard parser takes precedence for income)
    if "total_income" in standard_extracted:
        result["extracted"]["total_income"] = standard_extracted["total_income"]
        result["confidence"]["total_income"] = 0.9  # Standard parser = higher confidence

    # Merge all other fields
    for field, value in standard_extracted.items():
        if not field.startswith("_"):
            result["extracted"][field] = value
            if field not in result["confidence"]:
                result["confidence"][field] = 0.9  # Default high confidence for standard parsing

    # Copy internal flags
    for field in ["_is_correction", "_changed_field", "_response_type"]:
        if field in standard_extracted:
            result["extracted"][field] = standard_extracted[field]

    # 5b. Propagate clarification request if parser could not understand an amount
    if "_clarification_needed" in standard_extracted:
        clarification = standard_extracted["_clarification_needed"]
        result["needs_confirmation"].append({
            "field": clarification["field"],
            "value": None,
            "message": clarification["message"]
        })
        result["extracted"].pop("_clarification_needed", None)

    # 6. Check for ambiguous amounts
    ambiguous = EnhancedParser.detect_ambiguous_amounts(message)
    result["ambiguous"] = ambiguous

    # If we found an ambiguous bare number, ask for confirmation
    # This applies whether income was extracted or not, because the bare number IS ambiguous
    for amb in ambiguous:
        if amb.get("context") == "bare_number":
            extracted_income = result["extracted"].get("total_income")
            # Only flag if no income extracted, or if it matches the ambiguous bare number
            if extracted_income is None or extracted_income == amb["value"]:
                result["needs_confirmation"].append({
                    "field": "total_income",
                    "value": amb["interpretations"][1]["amount"],  # Assume thousands
                    "message": f"When you said '{amb['value']}', did you mean ${amb['interpretations'][1]['amount']:,.0f}?",
                    "options": amb["interpretations"]
                })
                # Set extracted value to the more likely interpretation (thousands)
                # This applies whether no income was extracted or if it matches the bare number
                result["extracted"]["total_income"] = amb["interpretations"][1]["amount"]
                result["confidence"]["total_income"] = 0.5  # Low confidence due to ambiguity

    # 7. Validate extracted data
    validation = EnhancedParser.validate_extracted_data(result["extracted"], current_profile)
    result["warnings"].extend(validation["warnings"])
    result["suggestions"].extend(validation["suggestions"])

    # Apply auto-corrections
    for field, corrected_value in validation.get("auto_corrections", {}).items():
        result["extracted"][field] = corrected_value

    # 8. Detect conflicts
    conflicts = EnhancedParser.detect_conflicts(message, result["extracted"], current_profile)
    result["conflicts"] = conflicts

    # 9. Adjust confidence based on hedging words
    for amb in ambiguous:
        if amb.get("type") == "hedging_detected":
            for field in result["confidence"]:
                result["confidence"][field] = max(0.5, result["confidence"][field] - amb["confidence_reduction"])

    return result


# Context tracking for smart follow-ups
class ConversationContext:
    """
    Tracks conversation context for smarter follow-up questions.
    """

    # Topic-specific follow-up questions
    FOLLOW_UPS = {
        "rental_income": [
            "How many rental properties do you have?",
            "What are your annual rental expenses (maintenance, insurance, etc.)?",
        ],
        "business_income": [
            "What type of business do you operate?",
            "Do you have a home office?",
            "How many business miles do you drive annually?",
        ],
        "investment_income": [
            "Did you have any capital gains or losses this year?",
            "Do you have qualified dividends?",
        ],
        "mortgage": [
            "How much mortgage interest did you pay this year?",
            "Did you pay any points on your mortgage?",
        ],
        "dependents": [
            "Are your dependents under 17 years old?",
            "Did you pay for childcare expenses?",
        ],
        "self_employed": [
            "What's your approximate business income?",
            "Do you have any business expenses to deduct?",
            "Do you work from home?",
        ],
        "retirement": [
            "How much did you contribute to your 401(k) this year?",
            "Do you have a traditional or Roth IRA?",
        ],
    }

    @classmethod
    def get_contextual_follow_up(cls, extracted: dict, current_profile: dict, session: dict = None) -> str:
        """
        Get a contextual follow-up question based on what was just discussed.
        Returns the question and marks it as asked so it won't repeat.
        """
        if session is None:
            return None

        asked = set(session.get("asked_follow_ups", []))

        for field, follow_ups in cls.FOLLOW_UPS.items():
            if field in extracted or extracted.get(f"has_{field}"):
                for question in follow_ups:
                    if question not in asked:
                        asked.add(question)
                        session["asked_follow_ups"] = list(asked)
                        return question

        return None

    @classmethod
    def detect_topic(cls, message: str) -> list:
        """
        Detect which tax topics are mentioned in the message.
        """
        import re
        topics = []
        msg_lower = message.lower()

        topic_patterns = {
            "rental_income": r'rental|landlord|tenant|property\s*income',
            "business_income": r'business|self[- ]?employ|1099|freelance|contractor',
            "investment_income": r'invest|stock|dividend|capital\s*gain|crypto|trading',
            "mortgage": r'mortgage|home\s*loan|house\s*payment',
            "dependents": r'child|kid|dependent|son|daughter',
            "self_employed": r'self[- ]?employ|own\s*business|freelance|contractor',
            "retirement": r'401k|ira|retire|pension',
            "education": r'student|college|tuition|education',
            "medical": r'medical|health|doctor|hospital',
            "charitable": r'donat|charit|church|tithe|non-?profit',
        }

        for topic, pattern in topic_patterns.items():
            if re.search(pattern, msg_lower):
                topics.append(topic)

        return topics


def detect_user_intent(message: str, profile: dict) -> str:
    """
    Detect the user's intent from their message.
    Returns: 'provide_info', 'ask_question', 'request_advice', 'correction', 'undo', 'generate_report'
    """
    import re
    msg_lower = message.lower().strip()

    # Undo/Reset intent
    if re.search(r'\bundo\b|\bgo\s*back\b|\bstart\s*over\b|\breset\b|\bbegin\s*again\b', msg_lower):
        return "undo"

    # Generate report intent
    if re.search(r'\breport\b|\bpdf\b|\bgenerate\b|\bdownload\b|\bsummary\b', msg_lower):
        return "generate_report"

    # Request advice intent
    if re.search(r'\badvice\b|\badvise\b|\brecommend|\bsuggest|\bstrateg|\bhelp\s*me\s*save|\bhow\s*can\s*i\b', msg_lower):
        return "request_advice"

    # Correction intent
    if re.search(r'\bactually\b|\bcorrect|\bwrong|\bmistake|\bchange\b|\binstead\b', msg_lower):
        return "correction"

    # Question intent
    if re.search(r'\?$|\bwhat\b|\bhow\b|\bwhy\b|\bwhen\b|\bwhere\b|\bcan\s*(i|you)\b|\bshould\b', msg_lower):
        return "ask_question"

    # Default: providing information
    return "provide_info"
