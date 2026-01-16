from typing import Optional
from pydantic import BaseModel, Field


class ItemizedDeductions(BaseModel):
    """Itemized deduction details (Schedule A)"""
    medical_expenses: float = Field(default=0.0, ge=0)
    state_local_income_tax: float = Field(default=0.0, ge=0)
    state_local_sales_tax: float = Field(default=0.0, ge=0)
    real_estate_tax: float = Field(default=0.0, ge=0)
    personal_property_tax: float = Field(default=0.0, ge=0)
    mortgage_interest: float = Field(default=0.0, ge=0)
    points_paid: float = Field(default=0.0, ge=0)

    # Mortgage debt tracking for TCJA interest limitation (IRS Pub. 936)
    mortgage_principal: float = Field(
        default=0.0, ge=0,
        description="Outstanding mortgage principal balance for interest limitation"
    )
    is_grandfathered_debt: bool = Field(
        default=False,
        description="Mortgage originated before Dec 16, 2017 (uses $1M limit)"
    )
    home_equity_interest: float = Field(
        default=0.0, ge=0,
        description="Home equity debt interest (not deductible post-TCJA unless for home improvement)"
    )

    charitable_cash: float = Field(default=0.0, ge=0)
    charitable_non_cash: float = Field(default=0.0, ge=0)
    casualty_losses: float = Field(default=0.0, ge=0)

    # Gambling losses (BR-0501 to BR-0510)
    # Note: Deductible only up to gambling winnings - tracked separately
    gambling_losses: float = Field(
        default=0.0,
        ge=0,
        description="Gambling losses (deductible only up to gambling winnings)"
    )

    other_itemized: float = Field(default=0.0, ge=0)
    other_itemized_description: Optional[str] = None

    def get_limited_mortgage_interest(self, filing_status: str = "single") -> float:
        """
        Calculate mortgage interest deduction after applying TCJA limits.

        Per IRS Publication 936:
        - Post-TCJA limit (after Dec 15, 2017): $750,000 ($375,000 MFS)
        - Pre-TCJA grandfathered: $1,000,000 ($500,000 MFS)
        - Home equity interest: NOT deductible (unless for home improvement)
        - Limitation applied proportionally when debt exceeds limit

        Args:
            filing_status: Filing status for limit determination (MFS = halved limits)

        Returns:
            Limited mortgage interest + points deduction
        """
        # If no interest paid, nothing to deduct
        if self.mortgage_interest <= 0 and self.points_paid <= 0:
            return 0.0

        # Home equity interest is NOT deductible post-TCJA
        # (We track it separately but don't include it in deduction)

        # Determine debt limit based on grandfathered status and filing status
        is_mfs = filing_status == "married_separate"

        if self.is_grandfathered_debt:
            # Pre-TCJA: $1,000,000 limit ($500,000 MFS)
            debt_limit = 500000.0 if is_mfs else 1000000.0
        else:
            # Post-TCJA: $750,000 limit ($375,000 MFS)
            debt_limit = 375000.0 if is_mfs else 750000.0

        # If no principal provided, assume full deduction (backward compatibility)
        if self.mortgage_principal <= 0:
            return self.mortgage_interest + self.points_paid

        # If principal is under limit, full interest is deductible
        if self.mortgage_principal <= debt_limit:
            return self.mortgage_interest + self.points_paid

        # Apply proportional limitation
        # Limited Interest = Interest × (Debt Limit / Principal)
        limitation_ratio = debt_limit / self.mortgage_principal
        limited_interest = round(self.mortgage_interest * limitation_ratio, 2)
        limited_points = round(self.points_paid * limitation_ratio, 2)

        return limited_interest + limited_points

    def get_total_itemized(
        self,
        agi: float,
        gambling_winnings: float = 0.0,
        filing_status: str = "single"
    ) -> float:
        """
        Calculate total itemized deductions.

        Args:
            agi: Adjusted Gross Income
            gambling_winnings: Total gambling winnings (to limit gambling loss deduction)
            filing_status: Filing status for mortgage interest limit (MFS = halved limits)

        Notes:
            - Medical expenses only deductible above 7.5% of AGI
            - SALT capped at $10,000
            - Mortgage interest subject to TCJA limits ($750k/$1M debt)
            - Gambling losses only deductible up to gambling winnings
        """
        total = 0.0

        # Medical expenses (only above 7.5% of AGI)
        medical_threshold = agi * 0.075
        if self.medical_expenses > medical_threshold:
            total += self.medical_expenses - medical_threshold

        # State and local taxes (SALT cap at $10,000)
        salt = self.state_local_income_tax + self.state_local_sales_tax + \
               self.real_estate_tax + self.personal_property_tax
        total += min(salt, 10000.0)

        # Mortgage interest (subject to TCJA limits - IRS Pub. 936)
        total += self.get_limited_mortgage_interest(filing_status)

        # Charitable contributions
        total += self.charitable_cash + self.charitable_non_cash

        # Casualty losses
        total += self.casualty_losses

        # Gambling losses (BR-0501 to BR-0510)
        # Only deductible up to the amount of gambling winnings
        if self.gambling_losses > 0 and gambling_winnings > 0:
            deductible_gambling_losses = min(self.gambling_losses, gambling_winnings)
            total += deductible_gambling_losses

        # Other itemized
        total += self.other_itemized

        return total


class Deductions(BaseModel):
    """Tax deductions"""
    use_standard_deduction: bool = True
    itemized: ItemizedDeductions = Field(default_factory=ItemizedDeductions)
    
    # Above-the-line adjustments (reduce AGI)
    educator_expenses: float = Field(default=0.0, ge=0)
    student_loan_interest: float = Field(default=0.0, ge=0)
    hsa_contributions: float = Field(default=0.0, ge=0)
    ira_contributions: float = Field(default=0.0, ge=0)  # Traditional IRA
    roth_ira_contributions: float = Field(default=0.0, ge=0)  # Roth IRA (not deductible)
    self_employed_se_health: float = Field(default=0.0, ge=0)
    self_employed_sep_simple: float = Field(default=0.0, ge=0)
    penalty_early_withdrawal: float = Field(default=0.0, ge=0)
    alimony_paid: float = Field(default=0.0, ge=0)
    other_adjustments: float = Field(default=0.0, ge=0)
    
    def get_student_loan_interest_deduction(self, magi: float, filing_status: str) -> float:
        """
        Calculate student loan interest deduction with phaseout (BR2-0007, BR2-0008).

        Per IRS Publication 970 and Rev. Proc. 2024-40:
        - Maximum deduction: $2,500
        - MFS cannot claim this deduction
        - Single/HOH/QW: Phaseout begins at $85,000, ends at $100,000
        - MFJ: Phaseout begins at $170,000, ends at $200,000
        """
        if self.student_loan_interest <= 0:
            return 0.0

        # BR2-0007: Cap at $2,500
        base_deduction = min(self.student_loan_interest, 2500.0)

        # MFS cannot claim student loan interest deduction
        if filing_status == "married_separate":
            return 0.0

        # 2025 phaseout thresholds (IRS Rev. Proc. 2024-40)
        if filing_status == "married_joint":
            phaseout_start = 170000.0
            phaseout_end = 200000.0
        else:  # single, head_of_household, qualifying_widow
            phaseout_start = 85000.0
            phaseout_end = 100000.0

        # BR2-0008: Apply phaseout
        if magi <= phaseout_start:
            return base_deduction
        elif magi >= phaseout_end:
            return 0.0
        else:
            # Linear phaseout
            phaseout_range = phaseout_end - phaseout_start
            excess = magi - phaseout_start
            reduction_ratio = excess / phaseout_range
            return round(base_deduction * (1 - reduction_ratio), 2)

    def get_ira_deduction(
        self,
        magi: float,
        filing_status: str,
        is_covered_by_employer_plan: bool = False,
        spouse_covered_by_employer_plan: bool = False,
        is_age_50_plus: bool = False,
        taxable_compensation: float = 0.0,
    ) -> float:
        """
        Calculate Traditional IRA deduction with phaseout (BR2-0009, BR2-0010).

        Per IRS Publication 590-A for 2025:
        - Maximum contribution: $7,000 ($8,000 if age 50+)
        - Limited by taxable compensation
        - If not covered by any employer plan: full deduction regardless of income
        - If covered by employer plan: phaseout based on MAGI
        - If spouse covered (but taxpayer not): different phaseout thresholds

        2025 Phaseout thresholds when covered by employer plan:
        - Single/HOH: $79,000 - $89,000
        - MFJ: $126,000 - $146,000
        - MFS: $0 - $10,000

        2025 Phaseout when spouse covered (taxpayer not covered):
        - MFJ: $236,000 - $246,000
        - MFS: $0 - $10,000

        Args:
            magi: Modified Adjusted Gross Income for IRA purposes
            filing_status: Filing status for threshold lookup
            is_covered_by_employer_plan: Whether taxpayer is covered by employer retirement plan
            spouse_covered_by_employer_plan: Whether spouse is covered by employer plan
            is_age_50_plus: Whether taxpayer is age 50 or older (eligible for catchup)
            taxable_compensation: Taxpayer's taxable compensation (wages, SE income)

        Returns:
            Deductible IRA contribution amount after applying limits and phaseouts
        """
        if self.ira_contributions <= 0:
            return 0.0

        # Step 1: Apply contribution limit based on age
        # 2025 limits: $7,000 base, $8,000 if 50+
        contribution_limit = 8000.0 if is_age_50_plus else 7000.0
        limited_contribution = min(self.ira_contributions, contribution_limit)

        # Step 2: Apply compensation limit - cannot exceed taxable compensation
        if taxable_compensation <= 0:
            return 0.0
        contribution = min(limited_contribution, taxable_compensation)

        # Step 3: Determine if phaseout applies
        # If neither taxpayer nor spouse is covered by employer plan, full deduction
        if not is_covered_by_employer_plan and not spouse_covered_by_employer_plan:
            return contribution

        # Step 4: Determine which phaseout thresholds to use
        if is_covered_by_employer_plan:
            # Taxpayer is covered by employer plan
            phaseout_thresholds = self._get_ira_phaseout_covered(filing_status)
        else:
            # Only spouse is covered (taxpayer not covered)
            # Only applies to MFJ and MFS
            phaseout_thresholds = self._get_ira_phaseout_spouse_covered(filing_status)

        phaseout_start, phaseout_end = phaseout_thresholds

        # Step 5: Apply phaseout calculation
        if magi <= phaseout_start:
            return contribution
        elif magi >= phaseout_end:
            return 0.0
        else:
            # Linear phaseout
            phaseout_range = phaseout_end - phaseout_start
            excess = magi - phaseout_start
            reduction_ratio = excess / phaseout_range
            # IRS rounds to nearest $10 (round up to next $10 for partial amounts)
            reduced = contribution * (1 - reduction_ratio)
            # Per IRS Publication 590-A: round up to nearest $10, minimum $200
            if reduced > 0 and reduced < 200:
                return 200.0
            return round(reduced / 10) * 10  # Round to nearest $10

    def _get_ira_phaseout_covered(self, filing_status: str) -> tuple:
        """Get IRA phaseout thresholds when taxpayer is covered by employer plan."""
        # 2025 thresholds (IRS Publication 590-A)
        thresholds = {
            "single": (79000.0, 89000.0),
            "married_joint": (126000.0, 146000.0),
            "married_separate": (0.0, 10000.0),
            "head_of_household": (79000.0, 89000.0),
            "qualifying_widow": (126000.0, 146000.0),
        }
        return thresholds.get(filing_status, (79000.0, 89000.0))

    def _get_ira_phaseout_spouse_covered(self, filing_status: str) -> tuple:
        """Get IRA phaseout thresholds when only spouse is covered (taxpayer not covered)."""
        # 2025 thresholds (IRS Publication 590-A)
        # Only applies to married filing statuses
        thresholds = {
            "married_joint": (236000.0, 246000.0),
            "married_separate": (0.0, 10000.0),
        }
        # For non-married statuses, this shouldn't be called, but return no phaseout
        return thresholds.get(filing_status, (float('inf'), float('inf')))

    def get_roth_ira_eligible_contribution(
        self,
        magi: float,
        filing_status: str,
        is_age_50_plus: bool = False,
        taxable_compensation: float = 0.0,
        traditional_ira_contributions: float = 0.0,
    ) -> float:
        """
        Calculate eligible Roth IRA contribution with MAGI phaseout (BR2-0011).

        Per IRS Publication 590-A for 2025:
        - Maximum contribution: $7,000 ($8,000 if age 50+)
        - Combined Traditional + Roth cannot exceed limit
        - Limited by taxable compensation
        - Phaseout based on MAGI (no employer plan coverage test)
        - Roth contributions are NOT tax-deductible (unlike Traditional IRA)

        2025 Phaseout thresholds (MAGI-based, all filers):
        - Single/HOH: $150,000 - $165,000
        - MFJ/QW: $236,000 - $246,000
        - MFS: $0 - $10,000

        Args:
            magi: Modified Adjusted Gross Income for Roth IRA purposes
            filing_status: Filing status for threshold lookup
            is_age_50_plus: Whether taxpayer is age 50 or older (eligible for catchup)
            taxable_compensation: Taxpayer's taxable compensation (wages, SE income)
            traditional_ira_contributions: Amount contributed to Traditional IRA

        Returns:
            Maximum eligible Roth IRA contribution after applying limits and phaseouts
        """
        if self.roth_ira_contributions <= 0:
            return 0.0

        # Step 1: Apply contribution limit based on age
        # 2025 limits: $7,000 base, $8,000 if 50+
        contribution_limit = 8000.0 if is_age_50_plus else 7000.0

        # Step 2: Account for Traditional IRA contributions (combined limit)
        remaining_limit = max(0.0, contribution_limit - traditional_ira_contributions)
        limited_contribution = min(self.roth_ira_contributions, remaining_limit)

        if limited_contribution <= 0:
            return 0.0

        # Step 3: Apply compensation limit - cannot exceed taxable compensation
        if taxable_compensation <= 0:
            return 0.0
        contribution = min(limited_contribution, taxable_compensation)

        # Step 4: Get phaseout thresholds based on filing status
        phaseout_start, phaseout_end = self._get_roth_ira_phaseout(filing_status)

        # Step 5: Apply phaseout calculation
        if magi <= phaseout_start:
            return contribution
        elif magi >= phaseout_end:
            return 0.0
        else:
            # Linear phaseout
            phaseout_range = phaseout_end - phaseout_start
            excess = magi - phaseout_start
            reduction_ratio = excess / phaseout_range
            # IRS rounds to nearest $10 (round up to next $10 for partial amounts)
            reduced = contribution * (1 - reduction_ratio)
            # Per IRS Publication 590-A: round up to nearest $10, minimum $200
            if reduced > 0 and reduced < 200:
                return 200.0
            return round(reduced / 10) * 10  # Round to nearest $10

    def _get_roth_ira_phaseout(self, filing_status: str) -> tuple:
        """Get Roth IRA phaseout thresholds based on filing status."""
        # 2025 thresholds (IRS Publication 590-A)
        thresholds = {
            "single": (150000.0, 165000.0),
            "married_joint": (236000.0, 246000.0),
            "married_separate": (0.0, 10000.0),
            "head_of_household": (150000.0, 165000.0),
            "qualifying_widow": (236000.0, 246000.0),
        }
        return thresholds.get(filing_status, (150000.0, 165000.0))

    def get_total_adjustments(
        self,
        magi: float = None,
        filing_status: str = None,
        is_covered_by_employer_plan: bool = False,
        spouse_covered_by_employer_plan: bool = False,
        is_age_50_plus: bool = False,
        taxable_compensation: float = 0.0,
    ) -> float:
        """
        Calculate total above-the-line adjustments.

        Note: If magi and filing_status are provided, student loan interest
        and IRA deductions will be calculated with phaseouts. Otherwise, raw values are used.

        Args:
            magi: Modified Adjusted Gross Income (for phaseout calculations)
            filing_status: Filing status for threshold lookup
            is_covered_by_employer_plan: Whether taxpayer is covered by employer retirement plan
            spouse_covered_by_employer_plan: Whether spouse is covered by employer plan
            is_age_50_plus: Whether taxpayer is age 50 or older
            taxable_compensation: Taxpayer's taxable compensation for IRA limit
        """
        # Calculate student loan interest with phaseout if parameters provided
        if magi is not None and filing_status is not None:
            student_loan_deduction = self.get_student_loan_interest_deduction(magi, filing_status)
        else:
            student_loan_deduction = min(self.student_loan_interest, 2500.0)  # Cap at $2,500

        # Calculate IRA deduction with phaseout if parameters provided
        if magi is not None and filing_status is not None and taxable_compensation > 0:
            ira_deduction = self.get_ira_deduction(
                magi=magi,
                filing_status=filing_status,
                is_covered_by_employer_plan=is_covered_by_employer_plan,
                spouse_covered_by_employer_plan=spouse_covered_by_employer_plan,
                is_age_50_plus=is_age_50_plus,
                taxable_compensation=taxable_compensation,
            )
        else:
            # Raw value capped at contribution limit
            contribution_limit = 8000.0 if is_age_50_plus else 7000.0
            ira_deduction = min(self.ira_contributions, contribution_limit)

        return (
            self.educator_expenses +
            student_loan_deduction +
            self.hsa_contributions +
            ira_deduction +
            self.self_employed_se_health +
            self.self_employed_sep_simple +
            self.penalty_early_withdrawal +
            self.alimony_paid +
            self.other_adjustments
        )
    
    def get_deduction_amount(
        self,
        filing_status: str,
        agi: float,
        is_over_65: bool = False,
        is_blind: bool = False,
        spouse_itemizes: bool = False,
        is_dual_status_alien: bool = False,
        can_be_claimed_as_dependent: bool = False,
        earned_income_for_dependent: float = 0.0,
        gambling_winnings: float = 0.0
    ) -> float:
        """
        Get deduction amount (standard or itemized, whichever is higher)
        Standard deduction amounts for 2025 tax year

        Special rules (IRS Pub 501):
        - BR2-0002: MFS + spouse itemizes = $0 standard deduction
        - BR2-0003: Dual-status alien = $0 standard deduction
        - BR2-0004: Dependent standard deduction = max($1,350, $450+earned income), capped at basic

        Args:
            gambling_winnings: Total gambling winnings (limits gambling loss deduction)
        """
        if not self.use_standard_deduction:
            itemized_total = self.itemized.get_total_itemized(agi, gambling_winnings, filing_status)
            standard = self._get_standard_deduction(
                filing_status, is_over_65, is_blind,
                spouse_itemizes, is_dual_status_alien,
                can_be_claimed_as_dependent, earned_income_for_dependent
            )
            return max(itemized_total, standard)

        return self._get_standard_deduction(
            filing_status, is_over_65, is_blind,
            spouse_itemizes, is_dual_status_alien,
            can_be_claimed_as_dependent, earned_income_for_dependent
        )

    def _get_standard_deduction(
        self,
        filing_status: str,
        is_over_65: bool,
        is_blind: bool,
        spouse_itemizes: bool = False,
        is_dual_status_alien: bool = False,
        can_be_claimed_as_dependent: bool = False,
        earned_income_for_dependent: float = 0.0
    ) -> float:
        """
        Get standard deduction for 2025 tax year (IRS Rev. Proc. 2024-40)

        Special rules:
        - BR2-0002: If MFS and spouse itemizes, standard deduction = $0
        - BR2-0003: If dual-status alien, standard deduction = $0
        - BR2-0004: If taxpayer can be claimed as dependent, use special formula
        """
        # BR2-0003: Dual-status alien gets $0 standard deduction
        if is_dual_status_alien:
            return 0.0

        # BR2-0002: MFS with spouse itemizing gets $0 standard deduction
        if filing_status == "married_separate" and spouse_itemizes:
            return 0.0

        # 2025 standard deduction amounts
        base_deductions = {
            "single": 15750.0,
            "married_joint": 31500.0,
            "married_separate": 15750.0,
            "head_of_household": 23625.0,
            "qualifying_widow": 31500.0,
        }

        base = base_deductions.get(filing_status, 15750.0)

        # BR2-0004: Dependent standard deduction formula
        # Greater of $1,350 or ($450 + earned income), capped at basic standard deduction
        if can_be_claimed_as_dependent:
            # 2025 dependent standard deduction limits (IRS Rev. Proc. 2024-40)
            dependent_minimum = 1350.0  # Minimum for dependents
            dependent_earned_income_base = 450.0  # Added to earned income

            # Calculate dependent's standard deduction
            earned_income_formula = dependent_earned_income_base + earned_income_for_dependent
            dependent_deduction = max(dependent_minimum, earned_income_formula)

            # Cap at the basic standard deduction for their filing status
            base = min(dependent_deduction, base)

        # Additional standard deduction for age/blindness (2025 amounts)
        additional = 0.0
        if is_over_65 or is_blind:
            if filing_status in ["single", "head_of_household"]:
                additional = 1950.0  # $1,950 for 65+ or blind (2025)
            elif filing_status in ["married_joint", "married_separate", "qualifying_widow"]:
                additional = 1550.0  # $1,550 per person for 65+ or blind (2025)

        # Can get additional for both age and blindness
        if is_over_65 and is_blind:
            additional *= 2

        return base + additional
