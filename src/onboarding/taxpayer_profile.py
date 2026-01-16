"""Taxpayer Profile.

Builds and manages taxpayer profiles based on collected information,
used to customize the interview flow and recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum


class TaxpayerComplexity(Enum):
    """Complexity level of the taxpayer's situation."""
    SIMPLE = "simple"  # W-2 only, standard deduction
    MODERATE = "moderate"  # Multiple income sources, may itemize
    COMPLEX = "complex"  # Business income, investments, many deductions
    PROFESSIONAL = "professional"  # Needs CPA assistance


class LifeSituation(Enum):
    """Major life situations that affect taxes."""
    STANDARD = "standard"
    NEW_JOB = "new_job"
    MARRIED = "married"
    DIVORCED = "divorced"
    NEW_PARENT = "new_parent"
    HOMEOWNER = "homeowner"
    STUDENT = "student"
    RETIRED = "retired"
    SELF_EMPLOYED = "self_employed"
    INVESTOR = "investor"
    MOVED_STATES = "moved_states"
    CAREGIVER = "caregiver"


@dataclass
class TaxpayerProfile:
    """Complete profile of a taxpayer for customizing the tax experience."""
    # Identity
    taxpayer_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None

    # Demographics
    age: Optional[int] = None
    is_blind: bool = False
    is_disabled: bool = False

    # Filing situation
    filing_status: Optional[str] = None
    is_married: bool = False
    spouse_works: bool = False

    # Dependents
    num_dependents: int = 0
    num_children_under_17: int = 0
    num_children_under_13: int = 0
    num_children_in_college: int = 0
    has_other_dependents: bool = False

    # Income characteristics
    income_sources: Set[str] = field(default_factory=set)
    has_w2_income: bool = False
    has_self_employment: bool = False
    has_business_income: bool = False
    has_investment_income: bool = False
    has_retirement_income: bool = False
    has_rental_income: bool = False
    estimated_agi: float = 0.0
    income_bracket: Optional[str] = None  # low, middle, high

    # Employment
    is_employee: bool = False
    is_self_employed: bool = False
    is_business_owner: bool = False
    has_multiple_jobs: bool = False
    works_from_home: bool = False

    # Property and assets
    is_homeowner: bool = False
    has_mortgage: bool = False
    has_rental_property: bool = False
    has_investment_accounts: bool = False
    has_crypto: bool = False

    # Deduction profile
    likely_itemizes: bool = False
    has_mortgage_interest: bool = False
    has_significant_charity: bool = False
    has_high_medical_expenses: bool = False
    has_high_salt: bool = False

    # Credits potential
    potential_ctc: bool = False  # Child Tax Credit
    potential_eitc: bool = False  # Earned Income Credit
    potential_education: bool = False  # Education Credits
    potential_saver: bool = False  # Saver's Credit
    potential_ev: bool = False  # EV Credit
    potential_energy: bool = False  # Residential Energy

    # Life situations
    life_situations: Set[LifeSituation] = field(default_factory=set)

    # State info
    state_of_residence: Optional[str] = None
    has_multi_state: bool = False
    states_with_income: Set[str] = field(default_factory=set)

    # Complexity assessment
    complexity: TaxpayerComplexity = TaxpayerComplexity.SIMPLE
    needs_professional: bool = False
    complexity_factors: List[str] = field(default_factory=list)

    # Documents expected
    expected_forms: Set[str] = field(default_factory=set)

    # Prior year info
    has_prior_year_data: bool = False
    prior_year_agi: Optional[float] = None
    prior_year_filing_status: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary."""
        return {
            "identity": {
                "first_name": self.first_name,
                "last_name": self.last_name,
                "email": self.email,
            },
            "demographics": {
                "age": self.age,
                "is_blind": self.is_blind,
                "is_disabled": self.is_disabled,
            },
            "filing": {
                "filing_status": self.filing_status,
                "is_married": self.is_married,
            },
            "dependents": {
                "total": self.num_dependents,
                "children_under_17": self.num_children_under_17,
                "children_under_13": self.num_children_under_13,
                "children_in_college": self.num_children_in_college,
            },
            "income": {
                "sources": list(self.income_sources),
                "estimated_agi": self.estimated_agi,
                "bracket": self.income_bracket,
            },
            "complexity": {
                "level": self.complexity.value,
                "factors": self.complexity_factors,
                "needs_professional": self.needs_professional,
            },
            "expected_forms": list(self.expected_forms),
            "state": self.state_of_residence,
        }


class ProfileBuilder:
    """
    Builds taxpayer profiles from collected data.

    Analyzes answers to build a comprehensive profile that's used
    to customize the interview flow and provide personalized
    recommendations.
    """

    # Income thresholds for 2025
    INCOME_THRESHOLDS = {
        "low": 50000,
        "middle": 150000,
        "high": 400000,
    }

    # EITC limits for 2025
    EITC_LIMITS = {
        "single": {0: 18591, 1: 49084, 2: 55768, 3: 59899},
        "married": {0: 25511, 1: 56004, 2: 62688, 3: 66819},
    }

    def build_profile(self, answers: Dict[str, Any]) -> TaxpayerProfile:
        """Build a profile from questionnaire answers."""
        profile = TaxpayerProfile()

        # Identity
        profile.first_name = answers.get("first_name")
        profile.last_name = answers.get("last_name")
        profile.email = answers.get("email")

        # Age
        birth_date = answers.get("birth_date")
        if birth_date:
            profile.age = self._calculate_age(birth_date)

        # Filing status
        profile.filing_status = answers.get("filing_status")
        profile.is_married = answers.get("marital_status") == "married"

        # Dependents
        self._process_dependents(profile, answers)

        # Income
        self._process_income(profile, answers)

        # Deductions
        self._process_deductions(profile, answers)

        # Credits
        self._process_credits(profile, answers)

        # Life situations
        self._identify_life_situations(profile, answers)

        # State
        profile.state_of_residence = answers.get("state_residence")
        profile.has_multi_state = answers.get("moved_during_year", False) or \
                                   answers.get("worked_other_state", False)

        # Determine complexity
        self._assess_complexity(profile)

        # Determine expected forms
        self._identify_expected_forms(profile, answers)

        return profile

    def update_profile(
        self, profile: TaxpayerProfile, new_answers: Dict[str, Any]
    ) -> TaxpayerProfile:
        """Update an existing profile with new answers."""
        # Re-process relevant sections
        self._process_income(profile, new_answers)
        self._process_deductions(profile, new_answers)
        self._process_credits(profile, new_answers)
        self._assess_complexity(profile)
        return profile

    def _calculate_age(self, birth_date: Any) -> int:
        """Calculate age from birth date."""
        from datetime import date

        if isinstance(birth_date, str):
            try:
                if "/" in birth_date:
                    parts = birth_date.split("/")
                    birth_date = date(int(parts[2]), int(parts[0]), int(parts[1]))
                else:
                    birth_date = date.fromisoformat(birth_date)
            except (ValueError, IndexError):
                return 30  # Default

        if isinstance(birth_date, date):
            today = date(2025, 12, 31)  # Tax year end
            return today.year - birth_date.year - (
                (today.month, today.day) < (birth_date.month, birth_date.day)
            )
        return 30

    def _process_dependents(
        self, profile: TaxpayerProfile, answers: Dict[str, Any]
    ) -> None:
        """Process dependent information."""
        has_dependents = answers.get("has_dependents", False)

        if has_dependents:
            children = int(answers.get("num_children", 0) or 0)
            other = int(answers.get("num_other_dependents", 0) or 0)

            profile.num_children_under_17 = children
            profile.num_dependents = children + other
            profile.has_other_dependents = other > 0

            # Estimate children under 13 for child care
            if children > 0:
                profile.num_children_under_13 = max(1, children // 2)

            # Check for college students
            profile.num_children_in_college = int(
                answers.get("num_college_students", 0) or 0
            )

            # CTC potential
            profile.potential_ctc = children > 0

    def _process_income(
        self, profile: TaxpayerProfile, answers: Dict[str, Any]
    ) -> None:
        """Process income information."""
        income_types = answers.get("income_types", [])
        if isinstance(income_types, str):
            income_types = [income_types]

        profile.income_sources = set(income_types)

        # Set flags
        profile.has_w2_income = "w2" in income_types
        profile.has_self_employment = "1099_nec" in income_types or "business" in income_types
        profile.has_business_income = "business" in income_types
        profile.has_investment_income = "investments" in income_types
        profile.has_retirement_income = "retirement" in income_types
        profile.has_rental_income = "rental" in income_types

        # Employment status
        profile.is_employee = profile.has_w2_income
        profile.is_self_employed = profile.has_self_employment
        profile.is_business_owner = profile.has_business_income
        profile.has_multiple_jobs = int(answers.get("num_w2s", 1) or 1) > 1

        # Estimate AGI
        estimated_agi = 0.0

        # W-2 wages
        wages = float(answers.get("w2_wages_1", 0) or 0)
        estimated_agi += wages

        # Add more W-2s if present
        for i in range(2, 6):
            additional_wages = float(answers.get(f"w2_wages_{i}", 0) or 0)
            estimated_agi += additional_wages

        # 1099 income
        for i in range(1, 6):
            nec = float(answers.get(f"1099_amount_{i}", 0) or 0)
            estimated_agi += nec

        # Business income (net)
        business_gross = float(answers.get("business_gross_income", 0) or 0)
        business_expenses = float(answers.get("business_expenses", 0) or 0)
        estimated_agi += max(0, business_gross - business_expenses)

        # Investment income
        dividends = float(answers.get("dividend_income", 0) or 0)
        interest = float(answers.get("interest_income", 0) or 0)
        cap_gains = float(answers.get("capital_gain_amount", 0) or 0)
        estimated_agi += dividends + interest + cap_gains

        # Retirement income
        ss_income = float(answers.get("ss_total", 0) or 0)
        pension = float(answers.get("pension_amount", 0) or 0)
        ira_dist = float(answers.get("ira_distribution_amount", 0) or 0)
        # Only ~85% of SS is taxable max
        estimated_agi += ss_income * 0.85 + pension + ira_dist

        profile.estimated_agi = estimated_agi

        # Determine income bracket
        if estimated_agi < self.INCOME_THRESHOLDS["low"]:
            profile.income_bracket = "low"
        elif estimated_agi < self.INCOME_THRESHOLDS["middle"]:
            profile.income_bracket = "middle"
        elif estimated_agi < self.INCOME_THRESHOLDS["high"]:
            profile.income_bracket = "high"
        else:
            profile.income_bracket = "very_high"

        # EITC potential
        status_key = "married" if profile.is_married else "single"
        children = min(3, profile.num_children_under_17)
        eitc_limit = self.EITC_LIMITS[status_key].get(children, 0)
        profile.potential_eitc = (
            estimated_agi <= eitc_limit and
            (profile.has_w2_income or profile.has_self_employment) and
            profile.filing_status != "married_separate"
        )

        # Home office
        profile.works_from_home = answers.get("home_office", False)

        # Crypto
        profile.has_crypto = answers.get("crypto_transactions", False)

    def _process_deductions(
        self, profile: TaxpayerProfile, answers: Dict[str, Any]
    ) -> None:
        """Process deduction information."""
        deduction_types = answers.get("deduction_types", [])
        if isinstance(deduction_types, str):
            deduction_types = [deduction_types]

        # Set flags
        profile.has_mortgage_interest = "mortgage" in deduction_types
        profile.is_homeowner = profile.has_mortgage_interest or "property_tax" in deduction_types
        profile.has_significant_charity = "charity" in deduction_types
        profile.has_high_medical_expenses = "medical" in deduction_types

        # SALT
        property_tax = float(answers.get("property_taxes", 0) or 0)
        state_tax = float(answers.get("state_local_income_tax", 0) or 0)
        profile.has_high_salt = (property_tax + state_tax) > 10000

        # Determine if likely to itemize
        mortgage = float(answers.get("mortgage_interest", 0) or 0)
        charity_cash = float(answers.get("charity_cash", 0) or 0)
        charity_noncash = float(answers.get("charity_noncash", 0) or 0)
        medical = float(answers.get("medical_expenses", 0) or 0)

        total_itemized = (
            mortgage +
            min(property_tax + state_tax, 10000) +  # SALT cap
            charity_cash + charity_noncash +
            max(0, medical - profile.estimated_agi * 0.075)  # 7.5% floor
        )

        # Compare to standard deduction (2025 amounts per IRS Rev. Proc. 2024-40)
        standard_deductions = {
            "single": 15750,
            "married_joint": 31500,
            "married_separate": 15750,
            "head_of_household": 23625,
        }
        standard = standard_deductions.get(profile.filing_status or "single", 15750)

        profile.likely_itemizes = total_itemized > standard
        profile.has_mortgage = profile.has_mortgage_interest

    def _process_credits(
        self, profile: TaxpayerProfile, answers: Dict[str, Any]
    ) -> None:
        """Process credit eligibility."""
        credit_situations = answers.get("credit_situations", [])
        if isinstance(credit_situations, str):
            credit_situations = [credit_situations]

        # Education credits
        profile.potential_education = "education" in credit_situations

        # Energy credits
        profile.potential_ev = "ev_purchase" in credit_situations
        profile.potential_energy = "home_energy" in credit_situations

        # Saver's credit (based on AGI)
        saver_limits = {
            "single": 38250,
            "married_joint": 76500,
            "head_of_household": 57375,
        }
        limit = saver_limits.get(profile.filing_status or "single", 38250)
        has_retirement = answers.get("w2_401k_1", False) or \
                        float(answers.get("w2_401k_amount_1", 0) or 0) > 0
        profile.potential_saver = has_retirement and profile.estimated_agi <= limit

    def _identify_life_situations(
        self, profile: TaxpayerProfile, answers: Dict[str, Any]
    ) -> None:
        """Identify major life situations."""
        situations = set()

        # Marriage
        if answers.get("marital_status") == "married":
            situations.add(LifeSituation.MARRIED)

        # Divorce (would need to ask)
        if answers.get("marital_status") == "divorced":
            situations.add(LifeSituation.DIVORCED)

        # New parent (children under 1)
        if profile.num_children_under_17 > 0:
            # Simplified - would check ages
            pass

        # Homeowner
        if profile.is_homeowner:
            situations.add(LifeSituation.HOMEOWNER)

        # Student
        if answers.get("student_name") == "self":
            situations.add(LifeSituation.STUDENT)

        # Retired
        if profile.has_retirement_income and not profile.has_w2_income:
            situations.add(LifeSituation.RETIRED)

        # Self-employed
        if profile.is_self_employed or profile.is_business_owner:
            situations.add(LifeSituation.SELF_EMPLOYED)

        # Investor
        if profile.has_investment_income:
            situations.add(LifeSituation.INVESTOR)

        # Moved states
        if answers.get("moved_during_year"):
            situations.add(LifeSituation.MOVED_STATES)

        profile.life_situations = situations

    def _assess_complexity(self, profile: TaxpayerProfile) -> None:
        """Assess the complexity of the tax situation."""
        factors = []
        complexity_score = 0

        # Income complexity
        if profile.has_self_employment:
            factors.append("Self-employment income (Schedule C)")
            complexity_score += 2

        if profile.has_business_income:
            factors.append("Business ownership")
            complexity_score += 3

        if profile.has_rental_income:
            factors.append("Rental property income (Schedule E)")
            complexity_score += 2

        if profile.has_investment_income:
            factors.append("Investment income")
            complexity_score += 1

        if profile.has_crypto:
            factors.append("Cryptocurrency transactions")
            complexity_score += 2

        if len(profile.income_sources) > 3:
            factors.append("Multiple income sources")
            complexity_score += 1

        # Deduction complexity
        if profile.likely_itemizes:
            factors.append("Itemized deductions")
            complexity_score += 1

        # State complexity
        if profile.has_multi_state:
            factors.append("Multi-state filing")
            complexity_score += 2

        # Other factors
        if profile.num_dependents > 3:
            factors.append("Multiple dependents")
            complexity_score += 1

        if profile.estimated_agi > 400000:
            factors.append("High income")
            complexity_score += 1

        if profile.age and profile.age >= 65:
            factors.append("Senior taxpayer (special provisions)")
            complexity_score += 0  # Not really more complex, just different

        # Determine level
        if complexity_score <= 1:
            profile.complexity = TaxpayerComplexity.SIMPLE
        elif complexity_score <= 4:
            profile.complexity = TaxpayerComplexity.MODERATE
        elif complexity_score <= 7:
            profile.complexity = TaxpayerComplexity.COMPLEX
        else:
            profile.complexity = TaxpayerComplexity.PROFESSIONAL
            profile.needs_professional = True

        profile.complexity_factors = factors

    def _identify_expected_forms(
        self, profile: TaxpayerProfile, answers: Dict[str, Any]
    ) -> None:
        """Identify expected tax forms based on profile."""
        forms = set()

        # Always need
        forms.add("Form 1040")

        # W-2s
        if profile.has_w2_income:
            num_w2s = int(answers.get("num_w2s", 1) or 1)
            for i in range(num_w2s):
                forms.add(f"W-2 (Employer #{i + 1})")

        # 1099s
        if "1099_nec" in profile.income_sources:
            num_1099s = int(answers.get("num_1099s", 1) or 1)
            for i in range(num_1099s):
                forms.add(f"1099-NEC (Client #{i + 1})")

        # Schedule C
        if profile.has_self_employment or profile.has_business_income:
            forms.add("Schedule C (Business)")

        # Investment forms
        if profile.has_investment_income:
            forms.add("1099-DIV (Dividends)")
            forms.add("1099-INT (Interest)")
            if answers.get("capital_gains"):
                forms.add("1099-B (Brokerage)")

        # Retirement
        if profile.has_retirement_income:
            if answers.get("social_security"):
                forms.add("SSA-1099 (Social Security)")
            if answers.get("pension_income") or answers.get("ira_distribution"):
                forms.add("1099-R (Retirement)")

        # Mortgage
        if profile.has_mortgage_interest:
            forms.add("1098 (Mortgage Interest)")

        # Education
        if profile.potential_education:
            forms.add("1098-T (Tuition)")
            if answers.get("student_loan_interest_paid"):
                forms.add("1098-E (Student Loan Interest)")

        # Healthcare
        if answers.get("marketplace_plan"):
            forms.add("1095-A (Health Marketplace)")

        profile.expected_forms = forms

    def get_recommended_interview_path(
        self, profile: TaxpayerProfile
    ) -> List[str]:
        """Get recommended interview sections based on profile."""
        sections = ["personal_info", "filing_status"]

        # Dependents
        if profile.num_dependents > 0 or profile.potential_ctc:
            sections.append("dependents")

        # Income sections based on sources
        sections.append("income_overview")

        if profile.has_w2_income:
            sections.append("income_w2")

        if "1099_nec" in profile.income_sources:
            sections.append("income_1099")

        if profile.has_business_income:
            sections.append("income_business")

        if profile.has_investment_income:
            sections.append("income_investments")

        if profile.has_retirement_income:
            sections.append("income_retirement")

        if "other" in profile.income_sources:
            sections.append("income_other")

        # Deductions
        sections.append("deductions_overview")

        if profile.has_mortgage_interest:
            sections.append("deductions_mortgage")

        if profile.has_high_salt or profile.is_homeowner:
            sections.append("deductions_taxes")

        if profile.has_significant_charity:
            sections.append("deductions_charity")

        if profile.has_high_medical_expenses:
            sections.append("deductions_medical")

        # Credits
        sections.append("credits_overview")

        if profile.potential_education:
            sections.append("credits_education")

        if profile.num_children_under_13 > 0:
            sections.append("credits_child")

        if profile.potential_ev or profile.potential_energy:
            sections.append("credits_energy")

        # Healthcare and state
        sections.append("healthcare")
        sections.append("state_info")

        return sections
