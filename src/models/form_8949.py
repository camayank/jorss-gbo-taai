"""
Form 8949 - Sales and Other Dispositions of Capital Assets

Implements IRS Form 8949 for reporting sales and exchanges of capital assets
including stocks, bonds, mutual funds, and other securities.

Reference: IRS Instructions for Form 8949
"""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from models._decimal_utils import money, to_decimal


class SecurityType(str, Enum):
    """Types of securities for Form 8949 reporting."""
    STOCK = "stock"
    BOND = "bond"
    MUTUAL_FUND = "mutual_fund"
    ETF = "etf"
    OPTION = "option"
    REIT = "reit"
    COMMODITY = "commodity"
    FUTURES = "futures"
    COLLECTIBLE = "collectible"
    QUALIFIED_SMALL_BUSINESS_STOCK = "qsbs"  # Section 1202
    SECTION_1244_STOCK = "section_1244"  # Small business stock loss
    OTHER = "other"


class Form8949Box(str, Enum):
    """
    Form 8949 reporting boxes based on 1099-B reporting and holding period.

    Part I - Short-term (held 1 year or less):
    - Box A: Basis reported to IRS on 1099-B
    - Box B: Basis NOT reported to IRS
    - Box C: No Form 1099-B received

    Part II - Long-term (held more than 1 year):
    - Box D: Basis reported to IRS on 1099-B
    - Box E: Basis NOT reported to IRS
    - Box F: No Form 1099-B received
    """
    A = "A"  # Short-term, basis reported to IRS
    B = "B"  # Short-term, basis not reported
    C = "C"  # Short-term, no 1099-B
    D = "D"  # Long-term, basis reported to IRS
    E = "E"  # Long-term, basis not reported
    F = "F"  # Long-term, no 1099-B


class AdjustmentCode(str, Enum):
    """
    Form 8949 Column (f) adjustment codes.

    Used when proceeds or basis needs adjustment from what's
    reported on Form 1099-B.
    """
    W = "W"  # Wash sale - loss disallowed
    B = "B"  # Basis adjustment (incorrect on 1099-B)
    H = "H"  # Holding period adjustment
    M = "M"  # Multiple adjustments apply
    S = "S"  # Form 1099-B shows incorrect basis
    T = "T"  # Loss limited per Section 1244 (up to $50k/$100k MFJ)
    O = "O"  # Other adjustment (specify)
    Q = "Q"  # Qualified Opportunity Zone adjustment
    X = "X"  # Sale of Section 1202 QSBS exclusion
    L = "L"  # Like-kind exchange (partial)
    D = "D"  # Market discount
    P = "P"  # Premium on bond
    R = "R"  # Reported in error
    N = "N"  # Nondeductible loss (related party, wash sale complete)


class WashSaleInfo(BaseModel):
    """
    Wash sale tracking per IRS Publication 550.

    A wash sale occurs when you sell securities at a loss and buy
    substantially identical securities within 30 days before or after.
    The loss is disallowed and added to the basis of the replacement shares.
    """
    is_wash_sale: bool = Field(default=False, description="Transaction is a wash sale")
    disallowed_loss: float = Field(default=0.0, ge=0, description="Loss amount disallowed")
    replacement_shares_date: Optional[str] = Field(
        None, description="Date replacement shares were acquired (YYYY-MM-DD)"
    )
    replacement_shares_quantity: float = Field(
        default=0.0, ge=0, description="Number of replacement shares"
    )
    basis_adjustment: float = Field(
        default=0.0, description="Amount added to replacement share basis"
    )
    # New fields for enforcement
    holding_period_adjustment_days: int = Field(
        default=0, description="Days to add to replacement shares holding period per IRC §1223"
    )
    is_permanent_disallowance: bool = Field(
        default=False, description="True if replacement in IRA - loss permanently disallowed"
    )
    replacement_account_type: Optional[str] = Field(
        None, description="Account type of replacement purchase (taxable, ira, 401k, etc.)"
    )

    def calculate_adjusted_loss(self, original_loss: float) -> float:
        """Calculate the allowable loss after wash sale adjustment."""
        if not self.is_wash_sale or original_loss >= 0:
            return original_loss
        # Loss is a negative number, disallowed_loss is positive
        return original_loss + self.disallowed_loss  # Reduces the loss (makes less negative)


class SecurityTransaction(BaseModel):
    """
    Individual security transaction for Form 8949.

    Represents a single sale or disposition of a capital asset,
    with all required information for Form 8949 and Schedule D.
    """
    # Security identification
    security_type: SecurityType = SecurityType.STOCK
    description: str = Field(description="Description of property (e.g., '100 sh XYZ Corp')")
    cusip: Optional[str] = Field(None, description="CUSIP number if available")
    ticker_symbol: Optional[str] = Field(None, description="Stock ticker symbol")

    # Transaction dates
    date_acquired: str = Field(description="Date acquired (YYYY-MM-DD or 'VARIOUS')")
    date_sold: str = Field(description="Date sold or disposed (YYYY-MM-DD)")

    # Amounts (Form 8949 columns)
    proceeds: float = Field(description="Sales price (column d)")
    cost_basis: float = Field(description="Cost or other basis (column e)")

    # Adjustments (columns f and g)
    adjustment_codes: List[AdjustmentCode] = Field(
        default_factory=list,
        description="Adjustment codes (column f)"
    )
    adjustment_amount: float = Field(
        default=0.0,
        description="Adjustment to gain or loss (column g)"
    )

    # Form 8949 box determination
    form_8949_box: Optional[Form8949Box] = Field(
        None,
        description="Which Form 8949 box (A-F)"
    )

    # 1099-B information
    reported_on_1099b: bool = Field(
        default=True,
        description="Transaction reported on Form 1099-B"
    )
    basis_reported_to_irs: bool = Field(
        default=True,
        description="Cost basis reported to IRS on 1099-B"
    )

    # Broker information
    broker_name: Optional[str] = None
    account_number: Optional[str] = None

    # Wash sale tracking
    wash_sale: Optional[WashSaleInfo] = None

    # Special situations
    is_covered_security: bool = Field(
        default=True,
        description="Security acquired after applicable date (basis tracking required)"
    )
    acquired_from_inheritance: bool = Field(
        default=False,
        description="Inherited security (stepped-up basis)"
    )
    acquired_from_gift: bool = Field(
        default=False,
        description="Gift security (carryover basis)"
    )
    is_qualified_small_business_stock: bool = Field(
        default=False,
        description="Qualifies for Section 1202 QSBS exclusion"
    )
    qsbs_exclusion_percentage: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="QSBS gain exclusion percentage (50%, 75%, or 100%)"
    )
    is_section_1244_stock: bool = Field(
        default=False,
        description="Qualifies for Section 1244 ordinary loss treatment"
    )

    # Quantity tracking
    shares_sold: float = Field(default=0.0, ge=0, description="Number of shares sold")

    @field_validator('date_sold')
    @classmethod
    def validate_date_sold(cls, v: str) -> str:
        """Validate date_sold format."""
        if v.upper() == 'VARIOUS':
            return v
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError("date_sold must be YYYY-MM-DD format or 'VARIOUS'")
        return v

    @field_validator('date_acquired')
    @classmethod
    def validate_date_acquired(cls, v: str) -> str:
        """Validate date_acquired format."""
        if v.upper() == 'VARIOUS':
            return v
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError("date_acquired must be YYYY-MM-DD format or 'VARIOUS'")
        return v

    def is_long_term(self) -> bool:
        """Determine if transaction is long-term (held > 1 year)."""
        if self.date_acquired.upper() == 'VARIOUS':
            # Default to long-term for various dates
            return True
        try:
            acquired = datetime.strptime(self.date_acquired, '%Y-%m-%d')
            sold = datetime.strptime(self.date_sold, '%Y-%m-%d')
            # Long-term is MORE than 1 year (366+ days to be safe with leap years)
            holding_days = (sold - acquired).days
            return holding_days > 365
        except (ValueError, TypeError):
            return False

    def calculate_gain_loss(self) -> float:
        """Calculate gain or loss before adjustments."""
        return self.proceeds - self.cost_basis

    def calculate_adjusted_gain_loss(self) -> float:
        """Calculate gain or loss after all adjustments (column h)."""
        base_gain_loss = self.calculate_gain_loss()

        # Apply adjustment_amount which includes wash sale and other adjustments
        # Note: wash sale disallowed loss is already captured in adjustment_amount
        # when apply_wash_sale() is called, so we don't double-count
        return base_gain_loss + self.adjustment_amount

    def determine_form_8949_box(self) -> Form8949Box:
        """Determine which Form 8949 box this transaction belongs in."""
        is_lt = self.is_long_term()

        if not self.reported_on_1099b:
            return Form8949Box.F if is_lt else Form8949Box.C
        elif not self.basis_reported_to_irs:
            return Form8949Box.E if is_lt else Form8949Box.B
        else:
            return Form8949Box.D if is_lt else Form8949Box.A

    def get_adjustment_code_string(self) -> str:
        """Get comma-separated adjustment codes for Form 8949."""
        if not self.adjustment_codes:
            return ""
        return ",".join(code.value for code in self.adjustment_codes)

    def apply_wash_sale(
        self,
        disallowed_loss: float,
        replacement_date: Optional[str] = None,
        replacement_quantity: float = 0.0
    ) -> None:
        """Apply wash sale adjustment to this transaction."""
        if self.wash_sale is None:
            self.wash_sale = WashSaleInfo()

        self.wash_sale.is_wash_sale = True
        self.wash_sale.disallowed_loss = abs(disallowed_loss)
        self.wash_sale.replacement_shares_date = replacement_date
        self.wash_sale.replacement_shares_quantity = replacement_quantity
        self.wash_sale.basis_adjustment = abs(disallowed_loss)

        # Add wash sale code to adjustments
        if AdjustmentCode.W not in self.adjustment_codes:
            self.adjustment_codes.append(AdjustmentCode.W)

        # Update adjustment amount (positive because it reduces the loss)
        self.adjustment_amount = abs(disallowed_loss)

    def apply_qsbs_exclusion(self) -> float:
        """
        Apply Section 1202 QSBS exclusion.

        Returns the excluded gain amount.
        """
        if not self.is_qualified_small_business_stock:
            return 0.0

        gain = max(0, self.calculate_gain_loss())
        exclusion = gain * (self.qsbs_exclusion_percentage / 100)

        if AdjustmentCode.X not in self.adjustment_codes:
            self.adjustment_codes.append(AdjustmentCode.X)

        self.adjustment_amount -= exclusion  # Reduces the gain
        return exclusion

    def get_section_1244_ordinary_loss(self, filing_status: str = "single") -> float:
        """
        Calculate ordinary loss under Section 1244 for small business stock.

        Section 1244 allows up to $50,000 ($100,000 MFJ) of loss on
        qualified small business stock to be treated as ordinary loss
        instead of capital loss.

        Returns the amount that can be treated as ordinary loss.
        """
        if not self.is_section_1244_stock:
            return 0.0

        loss = self.calculate_gain_loss()
        if loss >= 0:
            return 0.0  # No loss = no Section 1244 benefit

        # Maximum ordinary loss limits
        if filing_status in ["married_filing_jointly", "qualifying_surviving_spouse"]:
            max_ordinary = 100000.0
        else:
            max_ordinary = 50000.0

        # Return the lesser of actual loss or limit (as positive for ordinary loss)
        return min(abs(loss), max_ordinary)

    def generate_form_8949_line(self) -> dict:
        """Generate a dictionary representing one line of Form 8949."""
        box = self.form_8949_box or self.determine_form_8949_box()

        return {
            'description': self.description,
            'date_acquired': self.date_acquired,
            'date_sold': self.date_sold,
            'proceeds': float(money(self.proceeds)),
            'cost_basis': float(money(self.cost_basis)),
            'adjustment_codes': self.get_adjustment_code_string(),
            'adjustment_amount': float(money(self.adjustment_amount)),
            'gain_loss': float(money(self.calculate_adjusted_gain_loss())),
            'form_8949_box': box.value,
            'is_long_term': self.is_long_term(),
        }


class Form1099B(BaseModel):
    """
    Form 1099-B - Proceeds from Broker and Barter Exchange Transactions.

    Represents the data received from a broker on Form 1099-B,
    which feeds into Form 8949.
    """
    broker_name: str = Field(description="Payer/broker name")
    broker_tin: Optional[str] = Field(None, description="Broker TIN")

    # Box 1a-1g: Short-term transactions (covered)
    proceeds_short_term_covered: float = Field(
        default=0.0, description="Box 1a: Proceeds from short-term covered"
    )
    cost_basis_short_term_covered: float = Field(
        default=0.0, description="Box 1b: Cost basis short-term covered"
    )

    # Boxes for long-term covered
    proceeds_long_term_covered: float = Field(
        default=0.0, description="Proceeds from long-term covered"
    )
    cost_basis_long_term_covered: float = Field(
        default=0.0, description="Cost basis long-term covered"
    )

    # Boxes for non-covered transactions
    proceeds_short_term_noncovered: float = Field(
        default=0.0, description="Proceeds from short-term non-covered"
    )
    proceeds_long_term_noncovered: float = Field(
        default=0.0, description="Proceeds from long-term non-covered"
    )

    # Wash sale loss disallowed (reported by broker)
    wash_sale_loss_disallowed: float = Field(
        default=0.0, description="Box 1g: Wash sale loss disallowed"
    )

    # Accrued market discount
    accrued_market_discount: float = Field(
        default=0.0, description="Box 1f: Accrued market discount"
    )

    # Federal income tax withheld
    federal_tax_withheld: float = Field(
        default=0.0, ge=0, description="Box 4: Federal tax withheld"
    )

    # Individual transactions from this 1099-B
    transactions: List[SecurityTransaction] = Field(
        default_factory=list,
        description="Individual transactions reported on this 1099-B"
    )

    def get_net_short_term_gain_loss(self) -> float:
        """Calculate net short-term gain/loss from this 1099-B."""
        if self.transactions:
            return sum(
                t.calculate_adjusted_gain_loss()
                for t in self.transactions
                if not t.is_long_term()
            )
        # Fall back to summary amounts
        return (
            self.proceeds_short_term_covered - self.cost_basis_short_term_covered +
            self.proceeds_short_term_noncovered  # No basis available for non-covered
        )

    def get_net_long_term_gain_loss(self) -> float:
        """Calculate net long-term gain/loss from this 1099-B."""
        if self.transactions:
            return sum(
                t.calculate_adjusted_gain_loss()
                for t in self.transactions
                if t.is_long_term()
            )
        return (
            self.proceeds_long_term_covered - self.cost_basis_long_term_covered +
            self.proceeds_long_term_noncovered
        )


class Form8949Summary(BaseModel):
    """
    Summary totals for Form 8949 by box type.

    Used to aggregate transactions for Schedule D reporting.
    """
    # Part I - Short-term totals
    box_a_proceeds: float = 0.0
    box_a_cost_basis: float = 0.0
    box_a_adjustments: float = 0.0
    box_a_gain_loss: float = 0.0
    box_a_count: int = 0

    box_b_proceeds: float = 0.0
    box_b_cost_basis: float = 0.0
    box_b_adjustments: float = 0.0
    box_b_gain_loss: float = 0.0
    box_b_count: int = 0

    box_c_proceeds: float = 0.0
    box_c_cost_basis: float = 0.0
    box_c_adjustments: float = 0.0
    box_c_gain_loss: float = 0.0
    box_c_count: int = 0

    # Part II - Long-term totals
    box_d_proceeds: float = 0.0
    box_d_cost_basis: float = 0.0
    box_d_adjustments: float = 0.0
    box_d_gain_loss: float = 0.0
    box_d_count: int = 0

    box_e_proceeds: float = 0.0
    box_e_cost_basis: float = 0.0
    box_e_adjustments: float = 0.0
    box_e_gain_loss: float = 0.0
    box_e_count: int = 0

    box_f_proceeds: float = 0.0
    box_f_cost_basis: float = 0.0
    box_f_adjustments: float = 0.0
    box_f_gain_loss: float = 0.0
    box_f_count: int = 0

    # Wash sale totals
    total_wash_sale_disallowed: float = 0.0

    # Section 1202 QSBS exclusion
    total_qsbs_exclusion: float = 0.0

    # Section 1244 ordinary loss
    total_section_1244_ordinary_loss: float = 0.0

    def get_total_short_term_gain_loss(self) -> float:
        """Get total short-term gain/loss (Part I total)."""
        return self.box_a_gain_loss + self.box_b_gain_loss + self.box_c_gain_loss

    def get_total_long_term_gain_loss(self) -> float:
        """Get total long-term gain/loss (Part II total)."""
        return self.box_d_gain_loss + self.box_e_gain_loss + self.box_f_gain_loss

    def get_total_proceeds(self) -> float:
        """Get total proceeds from all transactions."""
        return (
            self.box_a_proceeds + self.box_b_proceeds + self.box_c_proceeds +
            self.box_d_proceeds + self.box_e_proceeds + self.box_f_proceeds
        )

    def get_total_cost_basis(self) -> float:
        """Get total cost basis from all transactions."""
        return (
            self.box_a_cost_basis + self.box_b_cost_basis + self.box_c_cost_basis +
            self.box_d_cost_basis + self.box_e_cost_basis + self.box_f_cost_basis
        )

    def get_transaction_count(self) -> int:
        """Get total number of transactions."""
        return (
            self.box_a_count + self.box_b_count + self.box_c_count +
            self.box_d_count + self.box_e_count + self.box_f_count
        )


class SecuritiesPortfolio(BaseModel):
    """
    Complete securities portfolio for Form 8949 and Schedule D.

    Aggregates all 1099-B forms and individual transactions for
    comprehensive capital gains/losses reporting.
    """
    # 1099-B forms received from brokers
    form_1099b_list: List[Form1099B] = Field(
        default_factory=list,
        description="Form 1099-B documents from brokers"
    )

    # Additional transactions not on 1099-B
    additional_transactions: List[SecurityTransaction] = Field(
        default_factory=list,
        description="Transactions not reported on 1099-B"
    )

    # Loss carryforward from prior years
    short_term_loss_carryforward: float = Field(
        default=0.0, ge=0,
        description="Short-term capital loss carryforward from prior year"
    )
    long_term_loss_carryforward: float = Field(
        default=0.0, ge=0,
        description="Long-term capital loss carryforward from prior year"
    )

    def get_all_transactions(self) -> List[SecurityTransaction]:
        """Get all transactions from all sources."""
        transactions = []
        for form_1099b in self.form_1099b_list:
            transactions.extend(form_1099b.transactions)
        transactions.extend(self.additional_transactions)
        return transactions

    def calculate_summary(self, filing_status: str = "single") -> Form8949Summary:
        """
        Calculate Form 8949 summary totals by box.

        Returns aggregated totals for Schedule D reporting.
        """
        summary = Form8949Summary()

        for transaction in self.get_all_transactions():
            box = transaction.form_8949_box or transaction.determine_form_8949_box()
            proceeds = transaction.proceeds
            basis = transaction.cost_basis
            adjustment = transaction.adjustment_amount
            gain_loss = transaction.calculate_adjusted_gain_loss()

            # Track wash sales
            if transaction.wash_sale and transaction.wash_sale.is_wash_sale:
                summary.total_wash_sale_disallowed += transaction.wash_sale.disallowed_loss

            # Track QSBS exclusions
            if transaction.is_qualified_small_business_stock:
                summary.total_qsbs_exclusion += transaction.apply_qsbs_exclusion()

            # Track Section 1244 ordinary loss
            if transaction.is_section_1244_stock:
                summary.total_section_1244_ordinary_loss += transaction.get_section_1244_ordinary_loss(filing_status)

            # Add to appropriate box
            if box == Form8949Box.A:
                summary.box_a_proceeds += proceeds
                summary.box_a_cost_basis += basis
                summary.box_a_adjustments += adjustment
                summary.box_a_gain_loss += gain_loss
                summary.box_a_count += 1
            elif box == Form8949Box.B:
                summary.box_b_proceeds += proceeds
                summary.box_b_cost_basis += basis
                summary.box_b_adjustments += adjustment
                summary.box_b_gain_loss += gain_loss
                summary.box_b_count += 1
            elif box == Form8949Box.C:
                summary.box_c_proceeds += proceeds
                summary.box_c_cost_basis += basis
                summary.box_c_adjustments += adjustment
                summary.box_c_gain_loss += gain_loss
                summary.box_c_count += 1
            elif box == Form8949Box.D:
                summary.box_d_proceeds += proceeds
                summary.box_d_cost_basis += basis
                summary.box_d_adjustments += adjustment
                summary.box_d_gain_loss += gain_loss
                summary.box_d_count += 1
            elif box == Form8949Box.E:
                summary.box_e_proceeds += proceeds
                summary.box_e_cost_basis += basis
                summary.box_e_adjustments += adjustment
                summary.box_e_gain_loss += gain_loss
                summary.box_e_count += 1
            elif box == Form8949Box.F:
                summary.box_f_proceeds += proceeds
                summary.box_f_cost_basis += basis
                summary.box_f_adjustments += adjustment
                summary.box_f_gain_loss += gain_loss
                summary.box_f_count += 1

        return summary

    def get_net_short_term_gain_loss(self) -> float:
        """Calculate net short-term gain/loss including carryforward."""
        summary = self.calculate_summary()
        return summary.get_total_short_term_gain_loss() - self.short_term_loss_carryforward

    def get_net_long_term_gain_loss(self) -> float:
        """Calculate net long-term gain/loss including carryforward."""
        summary = self.calculate_summary()
        return summary.get_total_long_term_gain_loss() - self.long_term_loss_carryforward

    def get_schedule_d_amounts(self) -> dict:
        """
        Get amounts for Schedule D reporting.

        Returns dictionary with Schedule D line items.
        """
        summary = self.calculate_summary()

        net_st = self.get_net_short_term_gain_loss()
        net_lt = self.get_net_long_term_gain_loss()
        overall_net = net_st + net_lt

        # Capital loss deduction limited to $3,000 per year
        capital_loss_deduction = 0.0
        new_st_carryforward = 0.0
        new_lt_carryforward = 0.0

        if overall_net < 0:
            # Loss situation - apply $3k limit
            total_loss = abs(overall_net)
            capital_loss_deduction = min(total_loss, 3000.0)
            excess_loss = total_loss - capital_loss_deduction

            if excess_loss > 0:
                # Allocate carryforward - short-term losses first
                if net_st < 0 and net_lt < 0:
                    st_loss = abs(net_st)
                    lt_loss = abs(net_lt)
                    # Use up to $3k proportionally
                    st_ratio = st_loss / total_loss
                    st_used = capital_loss_deduction * st_ratio
                    lt_used = capital_loss_deduction - st_used
                    new_st_carryforward = st_loss - st_used
                    new_lt_carryforward = lt_loss - lt_used
                elif net_st < 0:
                    new_st_carryforward = max(0, abs(net_st) - capital_loss_deduction)
                else:
                    new_lt_carryforward = max(0, abs(net_lt) - capital_loss_deduction)

        return {
            # Form 8949 Part I totals (short-term)
            'form_8949_box_a_gain_loss': float(money(summary.box_a_gain_loss)),
            'form_8949_box_b_gain_loss': float(money(summary.box_b_gain_loss)),
            'form_8949_box_c_gain_loss': float(money(summary.box_c_gain_loss)),

            # Form 8949 Part II totals (long-term)
            'form_8949_box_d_gain_loss': float(money(summary.box_d_gain_loss)),
            'form_8949_box_e_gain_loss': float(money(summary.box_e_gain_loss)),
            'form_8949_box_f_gain_loss': float(money(summary.box_f_gain_loss)),

            # Schedule D Part I (short-term)
            'schedule_d_line_1b': float(money(summary.box_a_gain_loss)),  # Box A total
            'schedule_d_line_2': float(money(summary.box_b_gain_loss)),   # Box B total
            'schedule_d_line_3': float(money(summary.box_c_gain_loss)),   # Box C total
            'schedule_d_line_6': float(money(self.short_term_loss_carryforward)),  # Prior year ST carryover
            'schedule_d_line_7': float(money(net_st)),  # Net short-term

            # Schedule D Part II (long-term)
            'schedule_d_line_8b': float(money(summary.box_d_gain_loss)),  # Box D total
            'schedule_d_line_9': float(money(summary.box_e_gain_loss)),   # Box E total
            'schedule_d_line_10': float(money(summary.box_f_gain_loss)),  # Box F total
            'schedule_d_line_14': float(money(self.long_term_loss_carryforward)),  # Prior year LT carryover
            'schedule_d_line_15': float(money(net_lt)),  # Net long-term

            # Schedule D Part III (summary)
            'schedule_d_line_16': float(money(overall_net)),  # Combined net gain/loss
            'capital_loss_deduction': float(money(capital_loss_deduction)),
            'new_short_term_carryforward': float(money(new_st_carryforward)),
            'new_long_term_carryforward': float(money(new_lt_carryforward)),

            # Additional tracking
            'total_wash_sale_disallowed': float(money(summary.total_wash_sale_disallowed)),
            'total_qsbs_exclusion': float(money(summary.total_qsbs_exclusion)),
            'total_section_1244_ordinary_loss': float(money(summary.total_section_1244_ordinary_loss)),
            'transaction_count': summary.get_transaction_count(),
        }

    def detect_wash_sales(self, lookback_days: int = 30, lookforward_days: int = 30) -> List[dict]:
        """
        Detect potential wash sales in the transaction list.

        A wash sale occurs when substantially identical securities are
        purchased within 30 days before or after a sale at a loss.

        Returns list of detected wash sales for review.
        """
        wash_sales = []
        transactions = self.get_all_transactions()

        # Sort by date
        dated_transactions = []
        for t in transactions:
            if t.date_sold.upper() != 'VARIOUS':
                try:
                    sold_date = datetime.strptime(t.date_sold, '%Y-%m-%d')
                    dated_transactions.append((sold_date, t))
                except ValueError:
                    continue

        dated_transactions.sort(key=lambda x: x[0])

        # Check each transaction for potential wash sale
        for i, (sold_date, transaction) in enumerate(dated_transactions):
            # Only check losses
            if transaction.calculate_gain_loss() >= 0:
                continue

            ticker = transaction.ticker_symbol or transaction.description

            # Look for substantially identical purchases in the window
            for j, (other_date, other_trans) in enumerate(dated_transactions):
                if i == j:
                    continue

                other_ticker = other_trans.ticker_symbol or other_trans.description

                # Check if substantially identical
                if ticker.lower() != other_ticker.lower():
                    continue

                # Check date acquired of the other transaction
                if other_trans.date_acquired.upper() == 'VARIOUS':
                    continue

                try:
                    acquired_date = datetime.strptime(other_trans.date_acquired, '%Y-%m-%d')
                except ValueError:
                    continue

                # Check if within wash sale window
                days_diff = (acquired_date - sold_date).days

                if -lookback_days <= days_diff <= lookforward_days:
                    wash_sales.append({
                        'loss_transaction': transaction.description,
                        'loss_date': transaction.date_sold,
                        'loss_amount': transaction.calculate_gain_loss(),
                        'replacement_transaction': other_trans.description,
                        'replacement_date': other_trans.date_acquired,
                        'days_difference': days_diff,
                    })

        return wash_sales

    def generate_form_8949_report(self) -> dict:
        """Generate complete Form 8949 report."""
        transactions = self.get_all_transactions()
        summary = self.calculate_summary()

        # Group transactions by box
        part_i = {'A': [], 'B': [], 'C': []}
        part_ii = {'D': [], 'E': [], 'F': []}

        for t in transactions:
            line = t.generate_form_8949_line()
            box = line['form_8949_box']
            if box in ['A', 'B', 'C']:
                part_i[box].append(line)
            else:
                part_ii[box].append(line)

        return {
            'part_i_short_term': {
                'box_a': {
                    'transactions': part_i['A'],
                    'totals': {
                        'proceeds': float(money(summary.box_a_proceeds)),
                        'cost_basis': float(money(summary.box_a_cost_basis)),
                        'adjustments': float(money(summary.box_a_adjustments)),
                        'gain_loss': float(money(summary.box_a_gain_loss)),
                    }
                },
                'box_b': {
                    'transactions': part_i['B'],
                    'totals': {
                        'proceeds': float(money(summary.box_b_proceeds)),
                        'cost_basis': float(money(summary.box_b_cost_basis)),
                        'adjustments': float(money(summary.box_b_adjustments)),
                        'gain_loss': float(money(summary.box_b_gain_loss)),
                    }
                },
                'box_c': {
                    'transactions': part_i['C'],
                    'totals': {
                        'proceeds': float(money(summary.box_c_proceeds)),
                        'cost_basis': float(money(summary.box_c_cost_basis)),
                        'adjustments': float(money(summary.box_c_adjustments)),
                        'gain_loss': float(money(summary.box_c_gain_loss)),
                    }
                },
                'total_short_term': float(money(summary.get_total_short_term_gain_loss())),
            },
            'part_ii_long_term': {
                'box_d': {
                    'transactions': part_ii['D'],
                    'totals': {
                        'proceeds': float(money(summary.box_d_proceeds)),
                        'cost_basis': float(money(summary.box_d_cost_basis)),
                        'adjustments': float(money(summary.box_d_adjustments)),
                        'gain_loss': float(money(summary.box_d_gain_loss)),
                    }
                },
                'box_e': {
                    'transactions': part_ii['E'],
                    'totals': {
                        'proceeds': float(money(summary.box_e_proceeds)),
                        'cost_basis': float(money(summary.box_e_cost_basis)),
                        'adjustments': float(money(summary.box_e_adjustments)),
                        'gain_loss': float(money(summary.box_e_gain_loss)),
                    }
                },
                'box_f': {
                    'transactions': part_ii['F'],
                    'totals': {
                        'proceeds': float(money(summary.box_f_proceeds)),
                        'cost_basis': float(money(summary.box_f_cost_basis)),
                        'adjustments': float(money(summary.box_f_adjustments)),
                        'gain_loss': float(money(summary.box_f_gain_loss)),
                    }
                },
                'total_long_term': float(money(summary.get_total_long_term_gain_loss())),
            },
            'wash_sales_disallowed': float(money(summary.total_wash_sale_disallowed)),
            'qsbs_exclusion': float(money(summary.total_qsbs_exclusion)),
            'section_1244_ordinary_loss': float(money(summary.total_section_1244_ordinary_loss)),
        }
