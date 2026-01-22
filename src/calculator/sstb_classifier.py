"""
SSTB (Specified Service Trade or Business) Classification System

Implements IRC Section 199A(d)(2) determination logic for identifying
Specified Service Trades or Businesses that are subject to QBI deduction limitations.

Reference:
- IRC §199A(d)(2) - Definition of SSTB
- Prop. Reg. §1.199A-5 - Specified service trades or businesses and the trade or business of performing services as an employee
- IRS Notice 2019-07 - De minimis rules for SSTBs
"""

from typing import Optional, Tuple
from enum import Enum
from decimal import Decimal


class SSTBCategory(str, Enum):
    """
    Categories of Specified Service Trades or Businesses per IRC §199A(d)(2).

    These businesses face QBI deduction limitations once income exceeds threshold amounts.
    """
    # Health - IRC §199A(d)(2)(A)
    HEALTH = "health"  # Doctors, dentists, nurses, therapists, pharmacists, etc.

    # Law - IRC §199A(d)(2)(B)
    LAW = "law"  # Attorneys, paralegals, legal services

    # Accounting - IRC §199A(d)(2)(C)
    ACCOUNTING = "accounting"  # CPAs, tax preparers, bookkeepers, enrolled agents

    # Actuarial Science - IRC §199A(d)(2)(D)
    ACTUARIAL = "actuarial"  # Actuaries, actuarial services

    # Performing Arts - IRC §199A(d)(2)(E)
    PERFORMING_ARTS = "performing_arts"  # Actors, musicians, directors, entertainers

    # Consulting - IRC §199A(d)(2)(F)
    CONSULTING = "consulting"  # Management consultants, business advisors

    # Athletics - IRC §199A(d)(2)(G)
    ATHLETICS = "athletics"  # Professional athletes, coaches, sports agents

    # Financial Services - IRC §199A(d)(2)(H)
    FINANCIAL_SERVICES = "financial_services"  # Investment advisors, brokers, planners

    # Brokerage Services - IRC §199A(d)(2)(I)
    BROKERAGE = "brokerage"  # Real estate brokers, stock brokers, insurance brokers

    # Trading or dealing in securities, commodities, or partnership interests
    TRADING = "trading"  # Day traders, commodity traders (principal basis)

    # Reputation/Skill-Based - IRC §199A(d)(2)(J) - Catch-all
    REPUTATION_SKILL = "reputation_skill"  # Any business where principal asset is reputation/skill

    # NOT an SSTB
    NON_SSTB = "non_sstb"


class SSTBClassifier:
    """
    Determines whether a business qualifies as a Specified Service Trade or Business (SSTB).

    Implements IRC §199A(d)(2) classification rules with industry code mappings.
    """

    # NAICS codes that are SSTBs (6-digit codes)
    # Mapping based on Prop. Reg. §1.199A-5(b)
    SSTB_NAICS_CODES = {
        # Health (IRC §199A(d)(2)(A))
        "621111": SSTBCategory.HEALTH,  # Offices of physicians (except mental health)
        "621112": SSTBCategory.HEALTH,  # Offices of physicians, mental health specialists
        "621210": SSTBCategory.HEALTH,  # Offices of dentists
        "621310": SSTBCategory.HEALTH,  # Offices of chiropractors
        "621320": SSTBCategory.HEALTH,  # Offices of optometrists
        "621330": SSTBCategory.HEALTH,  # Offices of mental health practitioners
        "621340": SSTBCategory.HEALTH,  # Offices of physical/occupational/speech therapists
        "621391": SSTBCategory.HEALTH,  # Offices of podiatrists
        "621399": SSTBCategory.HEALTH,  # Offices of all other health practitioners
        "621410": SSTBCategory.HEALTH,  # Family planning centers
        "621420": SSTBCategory.HEALTH,  # Outpatient mental health centers
        "621491": SSTBCategory.HEALTH,  # HMO medical centers
        "621492": SSTBCategory.HEALTH,  # Kidney dialysis centers
        "621493": SSTBCategory.HEALTH,  # Freestanding ambulatory surgical centers
        "621498": SSTBCategory.HEALTH,  # All other outpatient care centers
        "621511": SSTBCategory.HEALTH,  # Medical laboratories
        "621512": SSTBCategory.HEALTH,  # Diagnostic imaging centers
        "621610": SSTBCategory.HEALTH,  # Home health care services
        "621910": SSTBCategory.HEALTH,  # Ambulance services
        "621991": SSTBCategory.HEALTH,  # Blood and organ banks
        "621999": SSTBCategory.HEALTH,  # All other misc ambulatory health care
        "622000": SSTBCategory.HEALTH,  # Hospitals (all types)
        "623000": SSTBCategory.HEALTH,  # Nursing and residential care facilities

        # Law (IRC §199A(d)(2)(B))
        "541110": SSTBCategory.LAW,  # Offices of lawyers
        "541191": SSTBCategory.LAW,  # Title abstract and settlement offices
        "541199": SSTBCategory.LAW,  # All other legal services

        # Accounting (IRC §199A(d)(2)(C))
        "541211": SSTBCategory.ACCOUNTING,  # Offices of CPAs
        "541213": SSTBCategory.ACCOUNTING,  # Tax preparation services
        "541214": SSTBCategory.ACCOUNTING,  # Payroll services
        "541219": SSTBCategory.ACCOUNTING,  # Other accounting services

        # Actuarial (IRC §199A(d)(2)(D))
        # Note: Actuaries typically classified under consulting or insurance
        "524298": SSTBCategory.ACTUARIAL,  # Actuarial services (if separate)

        # Performing Arts (IRC §199A(d)(2)(E))
        "711110": SSTBCategory.PERFORMING_ARTS,  # Theater companies
        "711120": SSTBCategory.PERFORMING_ARTS,  # Dance companies
        "711130": SSTBCategory.PERFORMING_ARTS,  # Musical groups and artists
        "711190": SSTBCategory.PERFORMING_ARTS,  # Other performing arts companies
        "711211": SSTBCategory.PERFORMING_ARTS,  # Sports teams and clubs
        "711212": SSTBCategory.PERFORMING_ARTS,  # Racetracks
        "711219": SSTBCategory.PERFORMING_ARTS,  # Other spectator sports
        "711310": SSTBCategory.PERFORMING_ARTS,  # Promoters with facilities
        "711320": SSTBCategory.PERFORMING_ARTS,  # Promoters without facilities
        "711410": SSTBCategory.PERFORMING_ARTS,  # Agents/managers for artists/entertainers
        "711510": SSTBCategory.PERFORMING_ARTS,  # Independent artists, writers, performers

        # Consulting (IRC §199A(d)(2)(F))
        "541611": SSTBCategory.CONSULTING,  # Administrative/general management consulting
        "541612": SSTBCategory.CONSULTING,  # Human resources consulting
        "541613": SSTBCategory.CONSULTING,  # Marketing consulting
        "541614": SSTBCategory.CONSULTING,  # Process/logistics consulting
        "541618": SSTBCategory.CONSULTING,  # Other management consulting
        "541690": SSTBCategory.CONSULTING,  # Other scientific/technical consulting

        # Financial Services (IRC §199A(d)(2)(H))
        "523110": SSTBCategory.FINANCIAL_SERVICES,  # Investment banking
        "523120": SSTBCategory.FINANCIAL_SERVICES,  # Securities brokerage
        "523130": SSTBCategory.FINANCIAL_SERVICES,  # Commodity contracts dealing
        "523140": SSTBCategory.FINANCIAL_SERVICES,  # Commodity brokerage
        "523210": SSTBCategory.FINANCIAL_SERVICES,  # Securities and commodity exchanges
        "523910": SSTBCategory.FINANCIAL_SERVICES,  # Misc intermediation
        "523920": SSTBCategory.FINANCIAL_SERVICES,  # Portfolio management
        "523930": SSTBCategory.FINANCIAL_SERVICES,  # Investment advice
        "523991": SSTBCategory.FINANCIAL_SERVICES,  # Trust, fiduciary services
        "523999": SSTBCategory.FINANCIAL_SERVICES,  # Misc financial investment
        "525100": SSTBCategory.FINANCIAL_SERVICES,  # Insurance and employee benefit funds
        "525910": SSTBCategory.FINANCIAL_SERVICES,  # Open-end investment funds
        "525920": SSTBCategory.FINANCIAL_SERVICES,  # Trusts, estates, agency accounts
        "525990": SSTBCategory.FINANCIAL_SERVICES,  # Other financial vehicles

        # Brokerage (IRC §199A(d)(2)(I))
        "531210": SSTBCategory.BROKERAGE,  # Offices of real estate agents/brokers
        "524210": SSTBCategory.BROKERAGE,  # Insurance agencies and brokerages

        # Athletics (IRC §199A(d)(2)(G))
        # Most athletic activities already under performing arts 711xxx
    }

    # Business type keyword mappings for when NAICS not available
    SSTB_KEYWORDS = {
        # Health
        "doctor": SSTBCategory.HEALTH,
        "physician": SSTBCategory.HEALTH,
        "dentist": SSTBCategory.HEALTH,
        "dental": SSTBCategory.HEALTH,
        "chiropractor": SSTBCategory.HEALTH,
        "therapist": SSTBCategory.HEALTH,
        "therapy": SSTBCategory.HEALTH,
        "medical": SSTBCategory.HEALTH,
        "healthcare": SSTBCategory.HEALTH,
        "health": SSTBCategory.HEALTH,
        "nurse": SSTBCategory.HEALTH,
        "pharmacy": SSTBCategory.HEALTH,
        "pharmacist": SSTBCategory.HEALTH,
        "psychologist": SSTBCategory.HEALTH,
        "counselor": SSTBCategory.HEALTH,
        "veterinary": SSTBCategory.HEALTH,
        "veterinarian": SSTBCategory.HEALTH,

        # Law
        "attorney": SSTBCategory.LAW,
        "lawyer": SSTBCategory.LAW,
        "legal": SSTBCategory.LAW,
        "law firm": SSTBCategory.LAW,
        "paralegal": SSTBCategory.LAW,

        # Accounting
        "accountant": SSTBCategory.ACCOUNTING,
        "accounting": SSTBCategory.ACCOUNTING,
        "bookkeeper": SSTBCategory.ACCOUNTING,
        "bookkeeping": SSTBCategory.ACCOUNTING,
        "tax preparer": SSTBCategory.ACCOUNTING,
        "tax preparation": SSTBCategory.ACCOUNTING,
        "cpa": SSTBCategory.ACCOUNTING,

        # Consulting
        "consultant": SSTBCategory.CONSULTING,
        "consulting": SSTBCategory.CONSULTING,
        "advisor": SSTBCategory.CONSULTING,
        "advisory": SSTBCategory.CONSULTING,

        # Financial Services
        "financial advisor": SSTBCategory.FINANCIAL_SERVICES,
        "financial planner": SSTBCategory.FINANCIAL_SERVICES,
        "investment advisor": SSTBCategory.FINANCIAL_SERVICES,
        "wealth management": SSTBCategory.FINANCIAL_SERVICES,
        "portfolio management": SSTBCategory.FINANCIAL_SERVICES,

        # Brokerage
        "broker": SSTBCategory.BROKERAGE,
        "brokerage": SSTBCategory.BROKERAGE,
        "real estate agent": SSTBCategory.BROKERAGE,
        "insurance agent": SSTBCategory.BROKERAGE,

        # Performing Arts
        "actor": SSTBCategory.PERFORMING_ARTS,
        "actress": SSTBCategory.PERFORMING_ARTS,
        "musician": SSTBCategory.PERFORMING_ARTS,
        "artist": SSTBCategory.PERFORMING_ARTS,
        "entertainer": SSTBCategory.PERFORMING_ARTS,
        "performer": SSTBCategory.PERFORMING_ARTS,

        # Athletics
        "athlete": SSTBCategory.ATHLETICS,
        "athletic": SSTBCategory.ATHLETICS,
        "sports": SSTBCategory.ATHLETICS,
        "coach": SSTBCategory.ATHLETICS,
    }

    @classmethod
    def classify_business(
        cls,
        business_name: Optional[str] = None,
        business_code: Optional[str] = None,
        business_description: Optional[str] = None,
    ) -> SSTBCategory:
        """
        Classify a business as SSTB or non-SSTB based on available information.

        Args:
            business_name: Name of the business
            business_code: NAICS code (6-digit)
            business_description: Description of business activities

        Returns:
            SSTBCategory enum value
        """
        # First try NAICS code (most authoritative)
        if business_code:
            # Try exact match
            if business_code in cls.SSTB_NAICS_CODES:
                return cls.SSTB_NAICS_CODES[business_code]

            # Try first 5 digits (industry group)
            if len(business_code) >= 5:
                code_5 = business_code[:5]
                for naics, category in cls.SSTB_NAICS_CODES.items():
                    if naics.startswith(code_5):
                        return category

            # Try first 4 digits (industry)
            if len(business_code) >= 4:
                code_4 = business_code[:4]
                for naics, category in cls.SSTB_NAICS_CODES.items():
                    if naics.startswith(code_4):
                        return category

        # Try keyword matching in business name
        if business_name:
            name_lower = business_name.lower()
            for keyword, category in cls.SSTB_KEYWORDS.items():
                if keyword in name_lower:
                    return category

        # Try keyword matching in description
        if business_description:
            desc_lower = business_description.lower()
            for keyword, category in cls.SSTB_KEYWORDS.items():
                if keyword in desc_lower:
                    return category

        # Default to non-SSTB if cannot determine
        return SSTBCategory.NON_SSTB

    @classmethod
    def is_sstb(
        cls,
        business_name: Optional[str] = None,
        business_code: Optional[str] = None,
        business_description: Optional[str] = None,
    ) -> bool:
        """
        Determine if a business is an SSTB (simple boolean).

        Args:
            business_name: Name of the business
            business_code: NAICS code (6-digit)
            business_description: Description of business activities

        Returns:
            True if business is an SSTB, False otherwise
        """
        category = cls.classify_business(business_name, business_code, business_description)
        return category != SSTBCategory.NON_SSTB

    @classmethod
    def check_de_minimis_exception(
        cls,
        sstb_gross_receipts: Decimal,
        total_gross_receipts: Decimal,
        taxable_income: Decimal,
    ) -> Tuple[bool, str]:
        """
        Check if de minimis exception applies per IRS Notice 2019-07.

        The de minimis rule allows a business with some SSTB activity to be treated
        as a non-SSTB if the SSTB portion is below threshold:
        - If taxable income ≤ $500K: 10% threshold
        - If taxable income > $500K: 5% threshold

        Args:
            sstb_gross_receipts: Gross receipts from SSTB activities
            total_gross_receipts: Total gross receipts from all activities
            taxable_income: Taxable income (before QBI deduction)

        Returns:
            Tuple of (exception_applies: bool, explanation: str)
        """
        if total_gross_receipts <= 0:
            return (False, "No gross receipts")

        sstb_percentage = (sstb_gross_receipts / total_gross_receipts) * 100

        # Determine threshold based on taxable income
        threshold_income = Decimal("500000")
        if taxable_income <= threshold_income:
            threshold_pct = Decimal("10")  # 10% for lower income
            threshold_label = "10% (income ≤ $500K)"
        else:
            threshold_pct = Decimal("5")   # 5% for higher income
            threshold_label = "5% (income > $500K)"

        exception_applies = sstb_percentage < threshold_pct

        explanation = (
            f"SSTB receipts: {sstb_percentage:.2f}% of total. "
            f"De minimis threshold: {threshold_label}. "
            f"Exception {'APPLIES' if exception_applies else 'does NOT apply'}."
        )

        return (exception_applies, explanation)


def classify_schedule_c_business(
    business_name: str,
    business_code: Optional[str] = None,
    principal_product_or_service: Optional[str] = None,
) -> SSTBCategory:
    """
    Classify a Schedule C business as SSTB or non-SSTB.

    Convenience function for Schedule C classification.

    Args:
        business_name: Name of the business (Schedule C Line C)
        business_code: Business activity code (Schedule C Line B)
        principal_product_or_service: Description of principal product/service (Schedule C Line D)

    Returns:
        SSTBCategory enum value
    """
    return SSTBClassifier.classify_business(
        business_name=business_name,
        business_code=business_code,
        business_description=principal_product_or_service,
    )
