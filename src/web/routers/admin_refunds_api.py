"""
Admin Refunds API.

Provides endpoints for platform admins to:
- Process refund requests
- View refund history
- Approve/reject refund requests
- Track refund status

All refund operations are logged for compliance.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import uuid4
from dataclasses import dataclass, asdict
import logging

from rbac.dependencies import require_auth, require_platform_admin, require_permission
from rbac.context import AuthContext
from rbac.permissions import Permission

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/refunds",
    tags=["Admin Refunds"],
    responses={403: {"description": "Insufficient permissions"}},
)

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class RefundRequest(BaseModel):
    """Request to create a refund."""
    subscription_id: str = Field(..., description="Subscription/transaction to refund")
    amount: float = Field(..., gt=0, description="Refund amount")
    reason: str = Field(..., min_length=10, max_length=1000, description="Reason for refund")
    firm_id: Optional[str] = Field(None, description="Firm ID (required for platform admins)")


class RefundDecision(BaseModel):
    """Request to approve or reject a refund."""
    status: str = Field(..., description="Decision: approved, rejected")
    notes: Optional[str] = Field(None, max_length=500, description="Notes about the decision")


# =============================================================================
# IN-MEMORY STORAGE (Replace with database in production)
# =============================================================================


@dataclass
class Refund:
    """A refund request."""
    refund_id: str
    subscription_id: str
    firm_id: str
    firm_name: str
    amount: float
    reason: str
    status: str  # pending, approved, rejected, processed, failed
    requested_by: str
    requested_at: datetime
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_notes: Optional[str] = None
    processed_at: Optional[datetime] = None
    transaction_id: Optional[str] = None  # Payment processor reference


# Thread-safe in-memory storage
_refunds: dict[str, Refund] = {}

# Mock subscription data (replace with actual billing lookup)
_mock_subscriptions = {
    "sub-001": {"firm_id": "firm-001", "firm_name": "ABC Tax Services", "amount": 99.00},
    "sub-002": {"firm_id": "firm-002", "firm_name": "XYZ Accounting", "amount": 199.00},
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _get_subscription_info(subscription_id: str) -> Optional[dict]:
    """Mock subscription lookup - replace with billing system query."""
    return _mock_subscriptions.get(subscription_id)


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get("")
async def list_refunds(
    ctx: AuthContext = Depends(require_platform_admin),
    status: Optional[str] = Query(None, description="Filter by status"),
    firm_id: Optional[str] = Query(None, description="Filter by firm"),
    limit: int = Query(50, le=200, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    List refund requests.

    Platform admins see all refunds.
    Filterable by status and firm.
    """
    refunds = list(_refunds.values())

    # Apply filters
    if status:
        refunds = [r for r in refunds if r.status == status]
    if firm_id:
        refunds = [r for r in refunds if r.firm_id == firm_id]

    # Sort by requested_at descending
    refunds.sort(key=lambda r: r.requested_at, reverse=True)

    # Paginate
    total = len(refunds)
    refunds = refunds[offset:offset + limit]

    return {
        "refunds": [asdict(r) for r in refunds],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("")
async def create_refund(
    data: RefundRequest,
    ctx: AuthContext = Depends(require_auth),
):
    """
    Create a refund request.

    Firm partners can request refunds for their firm.
    Platform admins can request refunds for any firm.
    """
    # Look up subscription
    subscription = _get_subscription_info(data.subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found"
        )

    # Determine firm context
    if ctx.is_platform:
        firm_id = data.firm_id or subscription.get("firm_id")
        firm_name = subscription.get("firm_name", "Unknown")
    else:
        firm_id = str(ctx.firm_id) if ctx.firm_id else str(ctx.user_id)
        firm_name = ctx.firm_name or "Unknown"

        # Verify firm owns this subscription
        if subscription.get("firm_id") != firm_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot request refund for another firm's subscription"
            )

    # Validate amount
    max_refund = subscription.get("amount", 0)
    if data.amount > max_refund:
        raise HTTPException(
            status_code=400,
            detail=f"Refund amount exceeds maximum ({max_refund})"
        )

    # Create refund
    refund = Refund(
        refund_id=str(uuid4()),
        subscription_id=data.subscription_id,
        firm_id=firm_id,
        firm_name=firm_name,
        amount=data.amount,
        reason=data.reason,
        status="pending",
        requested_by=str(ctx.user_id),
        requested_at=datetime.utcnow(),
    )

    _refunds[refund.refund_id] = refund

    logger.info(
        f"[AUDIT] Refund requested | refund_id={refund.refund_id} | "
        f"amount=${data.amount} | firm={firm_id} | "
        f"subscription={data.subscription_id} | requested_by={ctx.user_id}"
    )

    return {
        "refund": asdict(refund),
        "message": "Refund request created and pending review",
    }


@router.get("/pending")
async def list_pending_refunds(
    ctx: AuthContext = Depends(require_platform_admin),
):
    """
    List pending refund requests requiring action.

    Sorted by oldest first (FIFO processing).
    """
    pending = [r for r in _refunds.values() if r.status == "pending"]
    pending.sort(key=lambda r: r.requested_at)

    return {
        "refunds": [asdict(r) for r in pending],
        "count": len(pending),
    }


@router.get("/{refund_id}")
async def get_refund(
    refund_id: str,
    ctx: AuthContext = Depends(require_auth),
):
    """
    Get details about a specific refund request.
    """
    refund = _refunds.get(refund_id)
    if not refund:
        raise HTTPException(status_code=404, detail="Refund not found")

    # Check access
    if not ctx.is_platform:
        firm_id = str(ctx.firm_id) if ctx.firm_id else str(ctx.user_id)
        if refund.firm_id != firm_id:
            raise HTTPException(status_code=403, detail="Access denied")

    return {"refund": asdict(refund)}


@router.post("/{refund_id}/decision")
async def decide_refund(
    refund_id: str,
    data: RefundDecision,
    ctx: AuthContext = Depends(require_platform_admin),
):
    """
    Approve or reject a refund request.

    Only platform admins can make refund decisions.
    """
    refund = _refunds.get(refund_id)
    if not refund:
        raise HTTPException(status_code=404, detail="Refund not found")

    if refund.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Refund has already been {refund.status}"
        )

    if data.status not in ("approved", "rejected"):
        raise HTTPException(
            status_code=400,
            detail="Status must be 'approved' or 'rejected'"
        )

    refund.status = data.status
    refund.decided_by = str(ctx.user_id)
    refund.decided_at = datetime.utcnow()
    refund.decision_notes = data.notes

    logger.info(
        f"[AUDIT] Refund {data.status} | refund_id={refund_id} | "
        f"amount=${refund.amount} | firm={refund.firm_id} | "
        f"decided_by={ctx.user_id} | notes={data.notes or 'None'}"
    )

    # If approved, queue for processing
    if data.status == "approved":
        # In production, this would trigger the payment processor
        logger.info(f"Refund {refund_id} queued for payment processing")

    return {
        "refund": asdict(refund),
        "message": f"Refund {data.status}",
    }


@router.post("/{refund_id}/process")
async def process_refund(
    refund_id: str,
    ctx: AuthContext = Depends(require_platform_admin),
):
    """
    Process an approved refund (trigger payment).

    Only approved refunds can be processed.
    """
    refund = _refunds.get(refund_id)
    if not refund:
        raise HTTPException(status_code=404, detail="Refund not found")

    if refund.status != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Only approved refunds can be processed (current: {refund.status})"
        )

    # In production, call payment processor here
    # For now, simulate processing
    refund.status = "processed"
    refund.processed_at = datetime.utcnow()
    refund.transaction_id = f"txn_{uuid4().hex[:12]}"

    logger.info(
        f"[AUDIT] Refund processed | refund_id={refund_id} | "
        f"amount=${refund.amount} | transaction={refund.transaction_id} | "
        f"processed_by={ctx.user_id}"
    )

    return {
        "refund": asdict(refund),
        "message": "Refund processed successfully",
        "transaction_id": refund.transaction_id,
    }


@router.get("/stats/summary")
async def get_refund_stats(
    ctx: AuthContext = Depends(require_platform_admin),
):
    """
    Get refund statistics summary.

    Returns counts and totals by status.
    """
    refunds = list(_refunds.values())

    stats = {
        "total_requests": len(refunds),
        "by_status": {
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "processed": 0,
            "failed": 0,
        },
        "total_amount_requested": 0.0,
        "total_amount_processed": 0.0,
        "total_amount_pending": 0.0,
    }

    for r in refunds:
        stats["by_status"][r.status] = stats["by_status"].get(r.status, 0) + 1
        stats["total_amount_requested"] += r.amount

        if r.status == "processed":
            stats["total_amount_processed"] += r.amount
        elif r.status in ("pending", "approved"):
            stats["total_amount_pending"] += r.amount

    return stats
