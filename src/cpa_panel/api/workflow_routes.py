"""
CPA Panel Workflow Routes

Endpoints for return status management, approval workflow, and review queue.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import logging

from .common import (
    get_workflow_manager,
    get_approval_manager,
    get_tax_return_adapter,
)

logger = logging.getLogger(__name__)

workflow_router = APIRouter(tags=["CPA Workflow"])


# =============================================================================
# STATUS ENDPOINTS
# =============================================================================

@workflow_router.get("/returns/{session_id}/status")
async def get_return_status(session_id: str, request: Request):
    """
    Get the current workflow status of a return.

    Returns status and feature access based on approval state.
    """
    try:
        manager = get_workflow_manager()
        status = manager.get_status(session_id)
        features = manager.get_feature_access(session_id)

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "status": status.to_dict(),
            "features": features.to_dict(),
        })
    except Exception as e:
        logger.error(f"Error getting status for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@workflow_router.post("/returns/{session_id}/submit-for-review")
async def submit_for_review(session_id: str, request: Request):
    """Submit a return for CPA review (DRAFT → IN_REVIEW)."""
    from cpa_panel.workflow import WorkflowTransitionError

    try:
        manager = get_workflow_manager()
        status = manager.submit_for_review(session_id)

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "status": status.to_dict(),
            "message": "Return submitted for CPA review",
        })
    except WorkflowTransitionError as e:
        logger.warning(f"Invalid transition for {session_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error submitting for review: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# APPROVAL ENDPOINTS
# =============================================================================

@workflow_router.post("/returns/{session_id}/approve")
async def approve_return(session_id: str, request: Request):
    """
    CPA sign-off on a return (IN_REVIEW → CPA_APPROVED).

    Request body:
        - cpa_reviewer_id: CPA identifier (required)
        - cpa_reviewer_name: CPA name
        - review_notes: Optional notes
        - pin: Optional CPA PIN for signature
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    cpa_reviewer_id = body.get("cpa_reviewer_id")
    cpa_reviewer_name = body.get("cpa_reviewer_name", "CPA Reviewer")
    review_notes = body.get("review_notes")
    pin = body.get("pin")

    if not cpa_reviewer_id:
        raise HTTPException(status_code=400, detail="cpa_reviewer_id is required")

    try:
        manager = get_approval_manager()
        approval = manager.approve_return(
            session_id=session_id,
            cpa_reviewer_id=cpa_reviewer_id,
            cpa_reviewer_name=cpa_reviewer_name,
            review_notes=review_notes,
            pin=pin,
        )

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "approval": approval.to_dict(),
            "message": f"Return approved by {cpa_reviewer_name}",
        })
    except Exception as e:
        logger.error(f"Error approving return: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@workflow_router.post("/returns/{session_id}/revert")
async def revert_to_draft(session_id: str, request: Request):
    """
    Revert a return to DRAFT status (CPA action).

    Request body:
        - cpa_reviewer_id: CPA identifier (required)
        - reason: Reason for reverting (required)
    """
    from cpa_panel.workflow import WorkflowTransitionError

    try:
        body = await request.json()
    except Exception:
        body = {}

    cpa_reviewer_id = body.get("cpa_reviewer_id")
    reason = body.get("reason", "Needs revisions")

    if not cpa_reviewer_id:
        raise HTTPException(status_code=400, detail="cpa_reviewer_id is required")

    try:
        manager = get_workflow_manager()
        status = manager.revert_to_draft(
            session_id=session_id,
            cpa_reviewer_id=cpa_reviewer_id,
            reason=reason,
        )

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "status": status.to_dict(),
            "message": f"Return reverted to DRAFT: {reason}",
        })
    except WorkflowTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error reverting return: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@workflow_router.get("/returns/{session_id}/approval-certificate")
async def get_approval_certificate(session_id: str, request: Request):
    """
    Get approval certificate for an approved return.

    Returns certificate data for client presentation.
    """
    from cpa_panel.workflow.approval import ApprovalCertificate

    adapter = get_tax_return_adapter()
    tax_return = adapter.get_tax_return(session_id)

    if not tax_return:
        raise HTTPException(status_code=404, detail="Tax return not found for this session")

    try:
        manager = get_approval_manager()
        approval = manager.get_approval_record(session_id)

        if not approval:
            raise HTTPException(
                status_code=400,
                detail="Return is not CPA approved. Certificate not available."
            )

        summary_obj = adapter.get_summary(session_id)
        summary = {
            "tax_year": summary_obj.tax_year if summary_obj else 2025,
            "taxpayer_name": summary_obj.taxpayer_name if summary_obj else "",
            "gross_income": summary_obj.total_income if summary_obj else 0,
            "tax_liability": summary_obj.tax_liability if summary_obj else 0,
            "refund_or_owed": summary_obj.refund_or_owed if summary_obj else 0,
        }

        certificate = ApprovalCertificate.generate(approval, summary)

        return JSONResponse({
            "success": True,
            "certificate": certificate,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating certificate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# QUEUE ENDPOINTS
# =============================================================================

# IMPORTANT: /queue/counts must be defined BEFORE /queue/{status}
@workflow_router.get("/queue/counts")
async def get_queue_counts(request: Request):
    """Get counts of returns in each status."""
    try:
        manager = get_workflow_manager()

        if hasattr(manager, 'get_queue_counts'):
            counts = manager.get_queue_counts()
        else:
            from cpa_panel.workflow import ReturnStatus
            counts = {}
            for status in ReturnStatus:
                try:
                    returns = manager.list_by_status(status)
                    counts[status.value] = len(returns)
                except Exception:
                    counts[status.value] = 0

        return JSONResponse({
            "success": True,
            "counts": counts,
            "total": sum(counts.values()),
        })
    except Exception as e:
        logger.error(f"Error getting queue counts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@workflow_router.get("/queue/{status}")
async def get_review_queue(status: str, request: Request, limit: int = 100, offset: int = 0):
    """
    Get returns by workflow status for CPA queue.

    Args:
        status: Filter by status (DRAFT, IN_REVIEW, CPA_APPROVED)
        limit: Max results (default 100)
        offset: Pagination offset
    """
    from cpa_panel.workflow import ReturnStatus

    try:
        valid_status = ReturnStatus(status.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Must be one of: {', '.join(s.value for s in ReturnStatus)}"
        )

    try:
        manager = get_workflow_manager()
        returns = manager.list_by_status(valid_status, limit=limit, offset=offset)

        return JSONResponse({
            "success": True,
            "status": valid_status.value,
            "returns": [r.to_dict() for r in returns],
            "count": len(returns),
            "limit": limit,
            "offset": offset,
        })
    except Exception as e:
        logger.error(f"Error getting queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# SUMMARY ENDPOINT
# =============================================================================

@workflow_router.get("/returns/{session_id}/summary")
async def get_return_summary(session_id: str, request: Request):
    """
    Get a comprehensive summary of a return for CPA review.

    Combines status, tax data, and insights into one response.
    """
    try:
        workflow = get_workflow_manager()
        status = workflow.get_status(session_id)
        features = workflow.get_feature_access(session_id)

        adapter = get_tax_return_adapter()
        tax_summary = adapter.get_summary(session_id)

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "workflow": {
                "status": status.to_dict(),
                "features": features.to_dict(),
            },
            "tax_return": tax_summary.to_dict() if tax_summary else None,
            "has_tax_data": tax_summary is not None,
        })
    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
