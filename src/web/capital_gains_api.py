"""
Capital Gains & Form 8949 API

REST API endpoints for managing securities transactions,
Form 8949 calculations, and Schedule D reporting.
"""
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
from decimal import Decimal
import logging
import uuid

# Import Form 8949 models
try:
    from models.form_8949 import (
        SecurityTransaction,
        SecurityType,
        AdjustmentCode,
        Form8949Box,
        WashSaleInfo,
        Form1099B,
        SecuritiesPortfolio,
        Form8949Summary
    )
    FORM_8949_AVAILABLE = True
except ImportError:
    FORM_8949_AVAILABLE = False

# Import Schedule D
try:
    from models.schedule_d import ScheduleD, ScheduleDPart1, ScheduleDPart2, ScheduleDPart3
    SCHEDULE_D_AVAILABLE = True
except ImportError:
    SCHEDULE_D_AVAILABLE = False

# Import audit logger
try:
    from audit.audit_logger import audit_capital_gain, get_audit_logger
    AUDIT_AVAILABLE = True
except ImportError:
    AUDIT_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/capital-gains", tags=["Capital Gains / Form 8949"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class TransactionInput(BaseModel):
    """Input model for a securities transaction."""
    security_type: str = Field(default="stock", description="stock, bond, mutual_fund, option, crypto, other")
    security_description: str = Field(..., description="Description of the security (e.g., 'AAPL - Apple Inc.')")
    ticker_symbol: Optional[str] = None
    cusip: Optional[str] = None

    date_acquired: str = Field(..., description="Date acquired (YYYY-MM-DD or 'VARIOUS')")
    date_sold: str = Field(..., description="Date sold (YYYY-MM-DD)")

    proceeds: float = Field(..., ge=0, description="Sales proceeds")
    cost_basis: float = Field(..., ge=0, description="Cost basis")

    shares_sold: Optional[float] = Field(default=None, description="Number of shares sold")

    # Adjustments
    adjustment_codes: Optional[List[str]] = Field(default=None, description="Adjustment codes (W, B, H, etc.)")
    adjustment_amount: Optional[float] = Field(default=None, description="Adjustment amount")
    adjustment_description: Optional[str] = None

    # 1099-B reporting
    reported_on_1099b: bool = Field(default=True, description="Was this reported on 1099-B?")
    basis_reported_to_irs: bool = Field(default=True, description="Was basis reported to IRS?")
    is_covered_security: bool = Field(default=True, description="Is this a covered security?")

    # Wash sale
    is_wash_sale: bool = Field(default=False, description="Is this a wash sale?")
    wash_sale_disallowed_loss: Optional[float] = Field(default=None)

    # Special situations
    acquired_from_inheritance: bool = Field(default=False)
    acquired_from_gift: bool = Field(default=False)


class TransactionResponse(BaseModel):
    """Response model for a securities transaction."""
    transaction_id: str
    security_description: str
    date_acquired: str
    date_sold: str
    proceeds: float
    cost_basis: float
    gain_loss: float
    is_long_term: bool
    form_8949_box: str
    holding_days: int
    adjustment_codes: Optional[List[str]]
    wash_sale_disallowed: Optional[float]


class PortfolioSummaryResponse(BaseModel):
    """Summary of Form 8949 / Schedule D calculations."""
    total_short_term_gain_loss: float
    total_long_term_gain_loss: float
    net_capital_gain_loss: float
    capital_loss_deduction: float
    carryforward_amount: float
    carryforward_type: Optional[str]
    by_box: Dict[str, Dict[str, float]]


class Form8949ReportResponse(BaseModel):
    """Full Form 8949 report."""
    part1_short_term: Dict[str, Any]
    part2_long_term: Dict[str, Any]
    total_transactions: int
    wash_sales_detected: int
    generated_at: str


# =============================================================================
# IN-MEMORY STORAGE (replace with database in production)
# =============================================================================

# Session-based portfolio storage
_portfolios: Dict[str, SecuritiesPortfolio] = {}


def get_or_create_portfolio(session_id: str) -> SecuritiesPortfolio:
    """Get or create a portfolio for a session."""
    if session_id not in _portfolios:
        _portfolios[session_id] = SecuritiesPortfolio()
    return _portfolios[session_id]


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/session/{session_id}/transaction", response_model=TransactionResponse)
async def add_transaction(
    session_id: str,
    transaction: TransactionInput
):
    """
    Add a securities transaction to the session portfolio.

    The transaction will be categorized into the appropriate Form 8949 box
    based on holding period and 1099-B reporting status.
    """
    if not FORM_8949_AVAILABLE:
        raise HTTPException(status_code=501, detail="Form 8949 module not available")

    try:
        # Parse dates
        if transaction.date_acquired.upper() == "VARIOUS":
            acquired_date = None
        else:
            acquired_date = datetime.strptime(transaction.date_acquired, "%Y-%m-%d").date()

        sold_date = datetime.strptime(transaction.date_sold, "%Y-%m-%d").date()

        # Map security type
        security_type_map = {
            "stock": SecurityType.STOCK,
            "bond": SecurityType.BOND,
            "mutual_fund": SecurityType.MUTUAL_FUND,
            "etf": SecurityType.ETF,
            "option": SecurityType.OPTION,
            "reit": SecurityType.REIT,
            "commodity": SecurityType.COMMODITY,
            "futures": SecurityType.FUTURES,
            "crypto": SecurityType.COLLECTIBLE,  # Crypto taxed as property/collectible
            "collectible": SecurityType.COLLECTIBLE,
            "other": SecurityType.OTHER
        }
        sec_type = security_type_map.get(transaction.security_type.lower(), SecurityType.OTHER)

        # Map adjustment codes
        adj_codes = None
        if transaction.adjustment_codes:
            adj_codes = [AdjustmentCode(code.upper()) for code in transaction.adjustment_codes]

        # Create transaction
        txn_id = str(uuid.uuid4())[:8]

        security_txn = SecurityTransaction(
            security_type=sec_type,
            description=transaction.security_description,
            ticker_symbol=transaction.ticker_symbol,
            cusip=transaction.cusip,
            date_acquired=transaction.date_acquired,  # String format
            date_sold=transaction.date_sold,  # String format
            proceeds=transaction.proceeds,
            cost_basis=transaction.cost_basis,
            adjustment_codes=adj_codes if adj_codes else [],
            adjustment_amount=transaction.adjustment_amount if transaction.adjustment_amount else 0.0,
            reported_on_1099b=transaction.reported_on_1099b,
            basis_reported_to_irs=transaction.basis_reported_to_irs
        )

        # Handle wash sale
        if transaction.is_wash_sale and transaction.wash_sale_disallowed_loss:
            security_txn.wash_sale = WashSaleInfo(
                is_wash_sale=True,
                disallowed_loss=transaction.wash_sale_disallowed_loss,
                basis_adjustment=transaction.wash_sale_disallowed_loss
            )

        # Add to portfolio
        portfolio = get_or_create_portfolio(session_id)
        portfolio.additional_transactions.append(security_txn)

        # Calculate derived values
        gain_loss = security_txn.calculate_gain_loss()
        is_long_term = security_txn.is_long_term()
        form_8949_box = security_txn.determine_form_8949_box()

        # Calculate holding days
        holding_days = 0
        if security_txn.date_acquired.upper() != "VARIOUS":
            try:
                acquired = datetime.strptime(security_txn.date_acquired, "%Y-%m-%d")
                sold = datetime.strptime(security_txn.date_sold, "%Y-%m-%d")
                holding_days = (sold - acquired).days
            except ValueError:
                holding_days = 0

        # Audit log
        if AUDIT_AVAILABLE:
            audit_capital_gain(
                session_id=session_id,
                action="add",
                transaction_id=txn_id,
                transaction_data={
                    "security": transaction.security_description,
                    "proceeds": transaction.proceeds,
                    "cost_basis": transaction.cost_basis,
                    "gain_loss": float(gain_loss),
                    "holding_period": "long_term" if is_long_term else "short_term"
                }
            )

        return TransactionResponse(
            transaction_id=txn_id,
            security_description=security_txn.description,
            date_acquired=security_txn.date_acquired,
            date_sold=security_txn.date_sold,
            proceeds=security_txn.proceeds,
            cost_basis=security_txn.cost_basis,
            gain_loss=gain_loss,
            is_long_term=is_long_term,
            form_8949_box=form_8949_box.value,
            holding_days=holding_days,
            adjustment_codes=[c.value for c in security_txn.adjustment_codes] if security_txn.adjustment_codes else None,
            wash_sale_disallowed=security_txn.wash_sale.disallowed_loss if security_txn.wash_sale else None
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid data: {str(e)}")
    except Exception as e:
        logger.error(f"Error adding transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/transactions", response_model=List[TransactionResponse])
async def get_transactions(session_id: str):
    """
    Get all transactions for a session.
    """
    if not FORM_8949_AVAILABLE:
        raise HTTPException(status_code=501, detail="Form 8949 module not available")

    portfolio = get_or_create_portfolio(session_id)

    transactions = []
    for txn in portfolio.additional_transactions:
        # Calculate holding days
        holding_days = 0
        if txn.date_acquired.upper() != "VARIOUS":
            try:
                acquired = datetime.strptime(txn.date_acquired, "%Y-%m-%d")
                sold = datetime.strptime(txn.date_sold, "%Y-%m-%d")
                holding_days = (sold - acquired).days
            except ValueError:
                holding_days = 0

        transactions.append(TransactionResponse(
            transaction_id=str(uuid.uuid4())[:8],  # Generate ID if not stored
            security_description=txn.description,
            date_acquired=txn.date_acquired,
            date_sold=txn.date_sold,
            proceeds=txn.proceeds,
            cost_basis=txn.cost_basis,
            gain_loss=txn.calculate_gain_loss(),
            is_long_term=txn.is_long_term(),
            form_8949_box=txn.determine_form_8949_box().value,
            holding_days=holding_days,
            adjustment_codes=[c.value for c in txn.adjustment_codes] if txn.adjustment_codes else None,
            wash_sale_disallowed=txn.wash_sale.disallowed_loss if txn.wash_sale else None
        ))

    return transactions


@router.delete("/session/{session_id}/transaction/{transaction_id}")
async def delete_transaction(session_id: str, transaction_id: str):
    """
    Delete a transaction from the session.
    """
    if not FORM_8949_AVAILABLE:
        raise HTTPException(status_code=501, detail="Form 8949 module not available")

    portfolio = get_or_create_portfolio(session_id)

    # Find and remove transaction
    original_count = len(portfolio.additional_transactions)
    portfolio.additional_transactions = [
        txn for txn in portfolio.additional_transactions
        if txn.transaction_id != transaction_id
    ]

    if len(portfolio.additional_transactions) == original_count:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Audit log
    if AUDIT_AVAILABLE:
        audit_capital_gain(
            session_id=session_id,
            action="delete",
            transaction_id=transaction_id,
            transaction_data={"deleted": True}
        )

    return {"status": "deleted", "transaction_id": transaction_id}


@router.get("/session/{session_id}/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(session_id: str):
    """
    Get Form 8949 / Schedule D summary for a session.

    Returns totals by short-term vs long-term, by Form 8949 box,
    and calculates the capital loss deduction and carryforward.
    """
    if not FORM_8949_AVAILABLE:
        raise HTTPException(status_code=501, detail="Form 8949 module not available")

    portfolio = get_or_create_portfolio(session_id)
    summary = portfolio.calculate_summary()

    # Get totals from Form8949Summary object
    st_total = summary.get_total_short_term_gain_loss()
    lt_total = summary.get_total_long_term_gain_loss()
    net_total = st_total + lt_total

    # Calculate capital loss deduction (max $3,000)
    capital_loss_deduction = 0.0
    carryforward = 0.0
    carryforward_type = None

    if net_total < 0:
        capital_loss_deduction = min(abs(net_total), 3000.0)
        if abs(net_total) > 3000:
            carryforward = abs(net_total) - 3000.0
            # Determine carryforward allocation
            if st_total < 0 and lt_total >= 0:
                carryforward_type = "short_term"
            elif lt_total < 0 and st_total >= 0:
                carryforward_type = "long_term"
            else:
                carryforward_type = "mixed"

    # Build by_box dict from summary
    by_box = {
        "A": {"proceeds": summary.box_a_proceeds, "cost_basis": summary.box_a_cost_basis, "adjustments": summary.box_a_adjustments, "gain_loss": summary.box_a_gain_loss, "count": summary.box_a_count},
        "B": {"proceeds": summary.box_b_proceeds, "cost_basis": summary.box_b_cost_basis, "adjustments": summary.box_b_adjustments, "gain_loss": summary.box_b_gain_loss, "count": summary.box_b_count},
        "C": {"proceeds": summary.box_c_proceeds, "cost_basis": summary.box_c_cost_basis, "adjustments": summary.box_c_adjustments, "gain_loss": summary.box_c_gain_loss, "count": summary.box_c_count},
        "D": {"proceeds": summary.box_d_proceeds, "cost_basis": summary.box_d_cost_basis, "adjustments": summary.box_d_adjustments, "gain_loss": summary.box_d_gain_loss, "count": summary.box_d_count},
        "E": {"proceeds": summary.box_e_proceeds, "cost_basis": summary.box_e_cost_basis, "adjustments": summary.box_e_adjustments, "gain_loss": summary.box_e_gain_loss, "count": summary.box_e_count},
        "F": {"proceeds": summary.box_f_proceeds, "cost_basis": summary.box_f_cost_basis, "adjustments": summary.box_f_adjustments, "gain_loss": summary.box_f_gain_loss, "count": summary.box_f_count},
    }

    return PortfolioSummaryResponse(
        total_short_term_gain_loss=st_total,
        total_long_term_gain_loss=lt_total,
        net_capital_gain_loss=net_total,
        capital_loss_deduction=capital_loss_deduction,
        carryforward_amount=carryforward,
        carryforward_type=carryforward_type,
        by_box=by_box
    )


@router.get("/session/{session_id}/form-8949", response_model=Form8949ReportResponse)
async def get_form_8949_report(session_id: str):
    """
    Generate complete Form 8949 report for a session.

    Returns Part I (Short-Term) and Part II (Long-Term) with
    all transactions categorized by box (A-F).
    """
    if not FORM_8949_AVAILABLE:
        raise HTTPException(status_code=501, detail="Form 8949 module not available")

    portfolio = get_or_create_portfolio(session_id)
    report = portfolio.generate_form_8949_report()

    return Form8949ReportResponse(
        part1_short_term=report.get("part1_short_term", {}),
        part2_long_term=report.get("part2_long_term", {}),
        total_transactions=report.get("total_transactions", 0),
        wash_sales_detected=report.get("wash_sales_detected", 0),
        generated_at=datetime.now().isoformat()
    )


@router.post("/session/{session_id}/detect-wash-sales")
async def detect_wash_sales(session_id: str):
    """
    Automatically detect wash sales in the portfolio.

    Scans for substantially identical securities sold at a loss
    where replacement shares were purchased within 30 days before or after.
    """
    if not FORM_8949_AVAILABLE:
        raise HTTPException(status_code=501, detail="Form 8949 module not available")

    portfolio = get_or_create_portfolio(session_id)
    wash_sales = portfolio.detect_wash_sales()

    return {
        "session_id": session_id,
        "wash_sales_detected": len(wash_sales),
        "wash_sales": [
            {
                "security": ws.get("security_description"),
                "loss_date": str(ws.get("loss_date")),
                "disallowed_loss": float(ws.get("disallowed_loss", 0)),
                "replacement_date": str(ws.get("replacement_date")) if ws.get("replacement_date") else None
            }
            for ws in wash_sales
        ]
    }


@router.get("/session/{session_id}/schedule-d")
async def get_schedule_d_amounts(session_id: str):
    """
    Get Schedule D line amounts for a session.

    Returns amounts for Schedule D Part I (lines 1-7),
    Part II (lines 8-15), and Part III summary.
    """
    if not FORM_8949_AVAILABLE:
        raise HTTPException(status_code=501, detail="Form 8949 module not available")

    portfolio = get_or_create_portfolio(session_id)
    schedule_d = portfolio.get_schedule_d_amounts()

    return {
        "session_id": session_id,
        "schedule_d": schedule_d,
        "generated_at": datetime.now().isoformat()
    }


@router.post("/session/{session_id}/add-1099b")
async def add_1099b(
    session_id: str,
    broker_name: str = Body(...),
    broker_ein: Optional[str] = Body(None),
    short_term_proceeds: float = Body(0),
    short_term_cost: float = Body(0),
    long_term_proceeds: float = Body(0),
    long_term_cost: float = Body(0),
    wash_sale_loss: Optional[float] = Body(None),
    federal_tax_withheld: Optional[float] = Body(None)
):
    """
    Add a 1099-B form to the session portfolio.

    Used for consolidated broker statements where individual
    transactions are summarized.
    """
    if not FORM_8949_AVAILABLE:
        raise HTTPException(status_code=501, detail="Form 8949 module not available")

    try:
        form_1099b = Form1099B(
            broker_name=broker_name,
            broker_ein=broker_ein,
            short_term_covered_proceeds=Decimal(str(short_term_proceeds)),
            short_term_covered_cost=Decimal(str(short_term_cost)),
            long_term_covered_proceeds=Decimal(str(long_term_proceeds)),
            long_term_covered_cost=Decimal(str(long_term_cost)),
            wash_sale_loss=Decimal(str(wash_sale_loss)) if wash_sale_loss else Decimal("0"),
            federal_tax_withheld=Decimal(str(federal_tax_withheld)) if federal_tax_withheld else Decimal("0")
        )

        portfolio = get_or_create_portfolio(session_id)
        portfolio.form_1099b_list.append(form_1099b)

        # Audit log
        if AUDIT_AVAILABLE:
            logger_instance = get_audit_logger()
            logger_instance.log(
                event_type="tax_data.form_import",
                action="import_1099b",
                resource_type="form_1099b",
                resource_id=session_id,
                new_value={
                    "broker_name": broker_name,
                    "st_proceeds": short_term_proceeds,
                    "lt_proceeds": long_term_proceeds
                }
            )

        return {
            "status": "added",
            "broker_name": broker_name,
            "total_1099b_forms": len(portfolio.form_1099b_list)
        }

    except Exception as e:
        logger.error(f"Error adding 1099-B: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/{session_id}/set-carryforward")
async def set_loss_carryforward(
    session_id: str,
    short_term_carryforward: float = Body(0, ge=0),
    long_term_carryforward: float = Body(0, ge=0)
):
    """
    Set prior year capital loss carryforward amounts.

    These amounts are applied when calculating the current year
    capital gain/loss on Schedule D.
    """
    if not FORM_8949_AVAILABLE:
        raise HTTPException(status_code=501, detail="Form 8949 module not available")

    portfolio = get_or_create_portfolio(session_id)
    portfolio.short_term_loss_carryforward = Decimal(str(short_term_carryforward))
    portfolio.long_term_loss_carryforward = Decimal(str(long_term_carryforward))

    return {
        "status": "updated",
        "short_term_carryforward": short_term_carryforward,
        "long_term_carryforward": long_term_carryforward
    }


@router.get("/health")
async def capital_gains_health_check():
    """
    Check if capital gains API is operational.
    """
    return {
        "status": "operational" if FORM_8949_AVAILABLE else "unavailable",
        "form_8949_available": FORM_8949_AVAILABLE,
        "schedule_d_available": SCHEDULE_D_AVAILABLE,
        "audit_available": AUDIT_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    }
