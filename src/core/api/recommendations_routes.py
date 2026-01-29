"""
Core Tax Recommendations API Routes

Unified tax recommendation endpoints for all user types:
- AI-generated tax optimization recommendations
- Personalized tax strategies
- Actionable tax savings opportunities
- Recommendation tracking and implementation

Access control is automatically applied based on UserContext.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import Optional, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from uuid import uuid4
import json
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .auth_routes import get_current_user
from ..models.user import UserContext, UserType

# Database session dependency
try:
    from database.connection import get_async_session
except ImportError:
    # Fallback - mock session for development when database module not available
    async def _mock_session():
        yield None
    get_async_session = _mock_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["Core Tax Recommendations"])


# =============================================================================
# MODELS
# =============================================================================

class RecommendationCategory(str, Enum):
    DEDUCTION = "deduction"
    CREDIT = "credit"
    RETIREMENT = "retirement"
    INVESTMENT = "investment"
    TIMING = "timing"
    STRUCTURE = "structure"
    COMPLIANCE = "compliance"
    PLANNING = "planning"


class RecommendationPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationStatus(str, Enum):
    NEW = "new"
    VIEWED = "viewed"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


class ActionItem(BaseModel):
    """An actionable step for a recommendation."""
    step: int
    description: str
    completed: bool = False
    completed_at: Optional[datetime] = None


class TaxRecommendation(BaseModel):
    """Tax recommendation model."""
    id: str
    user_id: str
    firm_id: Optional[str] = None
    tax_return_id: Optional[str] = None

    title: str
    summary: str
    detailed_explanation: str
    category: RecommendationCategory
    priority: RecommendationPriority
    status: RecommendationStatus

    # Estimated impact
    estimated_savings_low: float
    estimated_savings_high: float
    confidence_score: float  # 0-100

    # Action items
    action_items: List[ActionItem] = []
    deadline: Optional[datetime] = None  # Tax deadline relevance

    # Tracking
    generated_by: str  # ai, cpa-{id}
    generated_at: datetime
    viewed_at: Optional[datetime] = None
    implemented_at: Optional[datetime] = None

    # References
    relevant_forms: List[str] = []
    irs_references: List[str] = []
    related_scenario_id: Optional[str] = None


class RecommendationSummary(BaseModel):
    """Summary view of recommendation."""
    id: str
    title: str
    category: RecommendationCategory
    priority: RecommendationPriority
    status: RecommendationStatus
    estimated_savings_low: float
    estimated_savings_high: float
    generated_at: datetime


class CreateRecommendationRequest(BaseModel):
    """Request to create a recommendation (CPA manual creation)."""
    user_id: str
    tax_return_id: Optional[str] = None
    title: str
    summary: str
    detailed_explanation: str
    category: RecommendationCategory
    priority: RecommendationPriority = RecommendationPriority.MEDIUM
    estimated_savings_low: float = 0
    estimated_savings_high: float = 0
    action_items: List[str] = []
    deadline: Optional[datetime] = None


class UpdateRecommendationRequest(BaseModel):
    """Request to update recommendation status."""
    status: Optional[RecommendationStatus] = None
    notes: Optional[str] = None


# =============================================================================
# DATABASE HELPERS
# =============================================================================

async def _ensure_recommendations_table(session: AsyncSession):
    """Create recommendations table if it doesn't exist."""
    create_table = text("""
        CREATE TABLE IF NOT EXISTS recommendations (
            recommendation_id UUID PRIMARY KEY,
            user_id VARCHAR(100) NOT NULL,
            firm_id UUID,
            tax_return_id UUID,
            title VARCHAR(500) NOT NULL,
            summary TEXT NOT NULL,
            detailed_explanation TEXT,
            category VARCHAR(50) NOT NULL,
            priority VARCHAR(20) NOT NULL DEFAULT 'medium',
            status VARCHAR(30) NOT NULL DEFAULT 'new',
            estimated_savings_low NUMERIC(12, 2) DEFAULT 0,
            estimated_savings_high NUMERIC(12, 2) DEFAULT 0,
            confidence_score NUMERIC(5, 2) DEFAULT 0,
            action_items JSONB DEFAULT '[]',
            deadline TIMESTAMP,
            generated_by VARCHAR(100) NOT NULL,
            generated_at TIMESTAMP NOT NULL,
            viewed_at TIMESTAMP,
            implemented_at TIMESTAMP,
            relevant_forms JSONB DEFAULT '[]',
            irs_references JSONB DEFAULT '[]',
            related_scenario_id UUID,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await session.execute(create_table)

    # Create indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_recommendations_user ON recommendations(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_recommendations_firm ON recommendations(firm_id)",
        "CREATE INDEX IF NOT EXISTS ix_recommendations_status ON recommendations(status)",
        "CREATE INDEX IF NOT EXISTS ix_recommendations_category ON recommendations(category)",
        "CREATE INDEX IF NOT EXISTS ix_recommendations_priority ON recommendations(priority)",
    ]
    for idx in indexes:
        await session.execute(text(idx))
    await session.commit()


def _parse_datetime(value) -> Optional[datetime]:
    """Parse datetime from various formats."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return None
    return None


def _row_to_recommendation(row) -> TaxRecommendation:
    """Convert database row to TaxRecommendation model."""
    # Row order: recommendation_id, user_id, firm_id, tax_return_id, title, summary,
    #            detailed_explanation, category, priority, status, estimated_savings_low,
    #            estimated_savings_high, confidence_score, action_items, deadline,
    #            generated_by, generated_at, viewed_at, implemented_at, relevant_forms,
    #            irs_references, related_scenario_id

    # Parse action_items from JSONB
    action_items_raw = row[13] if row[13] else []
    if isinstance(action_items_raw, str):
        action_items_raw = json.loads(action_items_raw)

    action_items = [
        ActionItem(
            step=item.get("step", i + 1),
            description=item.get("description", ""),
            completed=item.get("completed", False),
            completed_at=_parse_datetime(item.get("completed_at"))
        )
        for i, item in enumerate(action_items_raw)
    ]

    # Parse JSON arrays
    relevant_forms = row[19] if row[19] else []
    if isinstance(relevant_forms, str):
        relevant_forms = json.loads(relevant_forms)

    irs_references = row[20] if row[20] else []
    if isinstance(irs_references, str):
        irs_references = json.loads(irs_references)

    return TaxRecommendation(
        id=str(row[0]),
        user_id=row[1],
        firm_id=str(row[2]) if row[2] else None,
        tax_return_id=str(row[3]) if row[3] else None,
        title=row[4],
        summary=row[5],
        detailed_explanation=row[6] or "",
        category=RecommendationCategory(row[7]) if row[7] else RecommendationCategory.PLANNING,
        priority=RecommendationPriority(row[8]) if row[8] else RecommendationPriority.MEDIUM,
        status=RecommendationStatus(row[9]) if row[9] else RecommendationStatus.NEW,
        estimated_savings_low=float(row[10] or 0),
        estimated_savings_high=float(row[11] or 0),
        confidence_score=float(row[12] or 0),
        action_items=action_items,
        deadline=_parse_datetime(row[14]),
        generated_by=row[15] or "system",
        generated_at=_parse_datetime(row[16]) or datetime.utcnow(),
        viewed_at=_parse_datetime(row[17]),
        implemented_at=_parse_datetime(row[18]),
        relevant_forms=relevant_forms,
        irs_references=irs_references,
        related_scenario_id=str(row[21]) if row[21] else None
    )


async def _build_access_conditions(context: UserContext) -> tuple:
    """Build SQL conditions for role-based recommendation access."""
    conditions = []
    params = {}

    if context.user_type == UserType.PLATFORM_ADMIN:
        conditions.append("1=1")
    elif context.user_type == UserType.CPA_TEAM:
        # CPA team can see recommendations in their firm or created by them
        conditions.append(
            "(r.firm_id = :firm_id OR r.generated_by = :generated_by OR "
            "r.user_id IN (SELECT client_id::text FROM clients WHERE preparer_id IN "
            "(SELECT user_id FROM users WHERE firm_id = :firm_id)))"
        )
        params["firm_id"] = context.firm_id
        params["generated_by"] = f"cpa-{context.user_id}"
    elif context.user_type in [UserType.CPA_CLIENT, UserType.CONSUMER]:
        # Clients and consumers can only see their own recommendations
        conditions.append("r.user_id = :user_id")
        params["user_id"] = context.user_id
    else:
        # Default: only own recommendations
        conditions.append("r.user_id = :user_id")
        params["user_id"] = context.user_id

    return " AND ".join(conditions) if conditions else "1=1", params


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _can_access_recommendation(context: UserContext, rec: TaxRecommendation) -> bool:
    """Check if user can access a recommendation."""
    if context.user_type == UserType.PLATFORM_ADMIN:
        return True

    if rec.user_id == context.user_id:
        return True

    if context.user_type == UserType.CPA_TEAM:
        if rec.firm_id == context.firm_id:
            return True

    return False


def _can_modify_recommendation(context: UserContext, rec: TaxRecommendation) -> bool:
    """Check if user can modify a recommendation."""
    if context.user_type == UserType.PLATFORM_ADMIN:
        return True

    # Users can update status of their own recommendations
    if rec.user_id == context.user_id:
        return True

    if context.user_type == UserType.CPA_TEAM:
        if rec.firm_id == context.firm_id:
            return True

    return False


async def _get_recommendation_by_id(
    recommendation_id: str,
    session: AsyncSession
) -> Optional[TaxRecommendation]:
    """Get a recommendation by ID from database."""
    query = text("""
        SELECT recommendation_id, user_id, firm_id, tax_return_id, title, summary,
               detailed_explanation, category, priority, status, estimated_savings_low,
               estimated_savings_high, confidence_score, action_items, deadline,
               generated_by, generated_at, viewed_at, implemented_at, relevant_forms,
               irs_references, related_scenario_id
        FROM recommendations r
        WHERE recommendation_id = :recommendation_id
    """)
    result = await session.execute(query, {"recommendation_id": recommendation_id})
    row = result.fetchone()

    if row:
        return _row_to_recommendation(row)
    return None


# =============================================================================
# LIST & SEARCH ENDPOINTS
# =============================================================================

@router.get("", response_model=List[RecommendationSummary])
async def list_recommendations(
    context: UserContext = Depends(get_current_user),
    category: Optional[RecommendationCategory] = None,
    priority: Optional[RecommendationPriority] = None,
    status: Optional[RecommendationStatus] = None,
    user_id: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session)
):
    """
    List tax recommendations with role-based filtering.

    Access control:
    - Consumers/CPA Clients: See only their own recommendations
    - CPA Team: See recommendations in their firm
    - Platform Admins: See all recommendations
    """
    await _ensure_recommendations_table(session)

    # Build access conditions
    access_conditions, access_params = await _build_access_conditions(context)

    # Build filter conditions
    filter_conditions = []
    filter_params = {}

    if category:
        filter_conditions.append("r.category = :category")
        filter_params["category"] = category.value
    if priority:
        filter_conditions.append("r.priority = :priority")
        filter_params["priority"] = priority.value
    if status:
        filter_conditions.append("r.status = :status")
        filter_params["status"] = status.value
    if user_id:
        filter_conditions.append("r.user_id = :filter_user_id")
        filter_params["filter_user_id"] = user_id

    # Combine conditions
    all_conditions = [access_conditions]
    if filter_conditions:
        all_conditions.extend(filter_conditions)
    where_clause = " AND ".join(all_conditions)

    # Combine params
    all_params = {**access_params, **filter_params, "limit": limit, "offset": offset}

    query = text(f"""
        SELECT recommendation_id, title, category, priority, status,
               estimated_savings_low, estimated_savings_high, generated_at
        FROM recommendations r
        WHERE {where_clause}
        ORDER BY
            CASE priority
                WHEN 'high' THEN 0
                WHEN 'medium' THEN 1
                WHEN 'low' THEN 2
                ELSE 3
            END,
            estimated_savings_high DESC
        LIMIT :limit OFFSET :offset
    """)

    result = await session.execute(query, all_params)
    rows = result.fetchall()

    results = []
    for row in rows:
        results.append(RecommendationSummary(
            id=str(row[0]),
            title=row[1],
            category=RecommendationCategory(row[2]) if row[2] else RecommendationCategory.PLANNING,
            priority=RecommendationPriority(row[3]) if row[3] else RecommendationPriority.MEDIUM,
            status=RecommendationStatus(row[4]) if row[4] else RecommendationStatus.NEW,
            estimated_savings_low=float(row[5] or 0),
            estimated_savings_high=float(row[6] or 0),
            generated_at=_parse_datetime(row[7]) or datetime.utcnow()
        ))

    return results


@router.get("/my")
async def get_my_recommendations(
    context: UserContext = Depends(get_current_user),
    status: Optional[RecommendationStatus] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session)
):
    """Get current user's recommendations."""
    return await list_recommendations(
        context=context,
        user_id=context.user_id,
        status=status,
        limit=limit,
        offset=offset,
        session=session
    )


@router.get("/actionable")
async def get_actionable_recommendations(
    context: UserContext = Depends(get_current_user),
    limit: int = Query(50, le=100),
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session)
):
    """Get recommendations that need action (new or in_progress)."""
    await _ensure_recommendations_table(session)

    # Get recommendations with actionable statuses
    query = text("""
        SELECT recommendation_id, title, category, priority, status,
               estimated_savings_low, estimated_savings_high, generated_at
        FROM recommendations r
        WHERE r.user_id = :user_id
          AND r.status IN ('new', 'viewed', 'in_progress')
        ORDER BY
            CASE priority
                WHEN 'high' THEN 0
                WHEN 'medium' THEN 1
                WHEN 'low' THEN 2
                ELSE 3
            END,
            estimated_savings_high DESC
        LIMIT :limit OFFSET :offset
    """)

    result = await session.execute(query, {
        "user_id": context.user_id,
        "limit": limit,
        "offset": offset
    })
    rows = result.fetchall()

    results = []
    for row in rows:
        results.append(RecommendationSummary(
            id=str(row[0]),
            title=row[1],
            category=RecommendationCategory(row[2]) if row[2] else RecommendationCategory.PLANNING,
            priority=RecommendationPriority(row[3]) if row[3] else RecommendationPriority.MEDIUM,
            status=RecommendationStatus(row[4]) if row[4] else RecommendationStatus.NEW,
            estimated_savings_low=float(row[5] or 0),
            estimated_savings_high=float(row[6] or 0),
            generated_at=_parse_datetime(row[7]) or datetime.utcnow()
        ))

    return results


# =============================================================================
# CRUD ENDPOINTS
# =============================================================================

@router.get("/{recommendation_id}", response_model=TaxRecommendation)
async def get_recommendation(
    recommendation_id: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Get a specific recommendation with full details."""
    await _ensure_recommendations_table(session)

    rec = await _get_recommendation_by_id(recommendation_id, session)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found"
        )

    if not _can_access_recommendation(context, rec):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this recommendation"
        )

    # Mark as viewed if first time viewing
    if rec.status == RecommendationStatus.NEW:
        now = datetime.utcnow()
        update_query = text("""
            UPDATE recommendations
            SET status = 'viewed', viewed_at = :viewed_at, updated_at = :updated_at
            WHERE recommendation_id = :recommendation_id
        """)
        await session.execute(update_query, {
            "recommendation_id": recommendation_id,
            "viewed_at": now.isoformat(),
            "updated_at": now.isoformat()
        })
        await session.commit()

        # Update the returned object
        rec.status = RecommendationStatus.VIEWED
        rec.viewed_at = now

    return rec


@router.post("", response_model=TaxRecommendation)
async def create_recommendation(
    request: CreateRecommendationRequest,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Create a manual recommendation.

    Only CPA team and platform admins can create recommendations.
    """
    if context.user_type not in [UserType.CPA_TEAM, UserType.PLATFORM_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only CPA team or admins can create recommendations"
        )

    await _ensure_recommendations_table(session)

    now = datetime.utcnow()
    recommendation_id = str(uuid4())

    # Convert action item strings to ActionItem objects for storage
    action_items = [
        {"step": i + 1, "description": desc, "completed": False, "completed_at": None}
        for i, desc in enumerate(request.action_items)
    ]

    insert_query = text("""
        INSERT INTO recommendations (
            recommendation_id, user_id, firm_id, tax_return_id, title, summary,
            detailed_explanation, category, priority, status, estimated_savings_low,
            estimated_savings_high, confidence_score, action_items, deadline,
            generated_by, generated_at, relevant_forms, irs_references
        ) VALUES (
            :recommendation_id, :user_id, :firm_id, :tax_return_id, :title, :summary,
            :detailed_explanation, :category, :priority, :status, :estimated_savings_low,
            :estimated_savings_high, :confidence_score, :action_items, :deadline,
            :generated_by, :generated_at, :relevant_forms, :irs_references
        )
    """)

    await session.execute(insert_query, {
        "recommendation_id": recommendation_id,
        "user_id": request.user_id,
        "firm_id": context.firm_id,
        "tax_return_id": request.tax_return_id,
        "title": request.title,
        "summary": request.summary,
        "detailed_explanation": request.detailed_explanation,
        "category": request.category.value,
        "priority": request.priority.value,
        "status": RecommendationStatus.NEW.value,
        "estimated_savings_low": request.estimated_savings_low,
        "estimated_savings_high": request.estimated_savings_high,
        "confidence_score": 100,  # Manual recommendations have 100% confidence
        "action_items": json.dumps(action_items),
        "deadline": request.deadline.isoformat() if request.deadline else None,
        "generated_by": f"cpa-{context.user_id}",
        "generated_at": now.isoformat(),
        "relevant_forms": json.dumps([]),
        "irs_references": json.dumps([])
    })
    await session.commit()

    logger.info(f"Recommendation created: {recommendation_id} for {request.user_id} by {context.user_id}")

    # Fetch and return the created recommendation
    rec = await _get_recommendation_by_id(recommendation_id, session)
    return rec


@router.patch("/{recommendation_id}", response_model=TaxRecommendation)
async def update_recommendation(
    recommendation_id: str,
    request: UpdateRecommendationRequest,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Update a recommendation status."""
    await _ensure_recommendations_table(session)

    rec = await _get_recommendation_by_id(recommendation_id, session)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found"
        )

    if not _can_modify_recommendation(context, rec):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify this recommendation"
        )

    now = datetime.utcnow()
    update_fields = ["updated_at = :updated_at"]
    update_params = {"recommendation_id": recommendation_id, "updated_at": now.isoformat()}

    if request.status:
        update_fields.append("status = :status")
        update_params["status"] = request.status.value
        if request.status == RecommendationStatus.IMPLEMENTED:
            update_fields.append("implemented_at = :implemented_at")
            update_params["implemented_at"] = now.isoformat()

    update_query = text(f"""
        UPDATE recommendations
        SET {', '.join(update_fields)}
        WHERE recommendation_id = :recommendation_id
    """)
    await session.execute(update_query, update_params)
    await session.commit()

    logger.info(f"Recommendation updated: {recommendation_id} by {context.user_id}")

    # Fetch and return updated recommendation
    rec = await _get_recommendation_by_id(recommendation_id, session)
    return rec


@router.delete("/{recommendation_id}")
async def delete_recommendation(
    recommendation_id: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Delete a recommendation (CPAs only)."""
    if context.user_type not in [UserType.CPA_TEAM, UserType.PLATFORM_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only CPA team or admins can delete recommendations"
        )

    await _ensure_recommendations_table(session)

    rec = await _get_recommendation_by_id(recommendation_id, session)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found"
        )

    if not _can_modify_recommendation(context, rec):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    delete_query = text("DELETE FROM recommendations WHERE recommendation_id = :recommendation_id")
    await session.execute(delete_query, {"recommendation_id": recommendation_id})
    await session.commit()

    logger.info(f"Recommendation deleted: {recommendation_id} by {context.user_id}")

    return {"success": True, "message": "Recommendation deleted"}


# =============================================================================
# ACTION TRACKING
# =============================================================================

@router.post("/{recommendation_id}/actions/{step}/complete")
async def complete_action_item(
    recommendation_id: str,
    step: int,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Mark an action item as complete."""
    await _ensure_recommendations_table(session)

    rec = await _get_recommendation_by_id(recommendation_id, session)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found"
        )

    if not _can_modify_recommendation(context, rec):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Find and update the action item
    now = datetime.utcnow()
    step_found = False
    updated_action_items = []

    for item in rec.action_items:
        item_dict = {
            "step": item.step,
            "description": item.description,
            "completed": item.completed,
            "completed_at": item.completed_at.isoformat() if item.completed_at else None
        }
        if item.step == step:
            item_dict["completed"] = True
            item_dict["completed_at"] = now.isoformat()
            step_found = True
        updated_action_items.append(item_dict)

    if not step_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action item step {step} not found"
        )

    # Determine new status
    all_completed = all(item["completed"] for item in updated_action_items)
    if all_completed:
        new_status = RecommendationStatus.IMPLEMENTED.value
        implemented_at = now.isoformat()
    elif rec.status in [RecommendationStatus.NEW, RecommendationStatus.VIEWED]:
        new_status = RecommendationStatus.IN_PROGRESS.value
        implemented_at = None
    else:
        new_status = rec.status.value
        implemented_at = None

    # Update database
    update_query = text("""
        UPDATE recommendations
        SET action_items = :action_items,
            status = :status,
            implemented_at = COALESCE(:implemented_at, implemented_at),
            updated_at = :updated_at
        WHERE recommendation_id = :recommendation_id
    """)
    await session.execute(update_query, {
        "recommendation_id": recommendation_id,
        "action_items": json.dumps(updated_action_items),
        "status": new_status,
        "implemented_at": implemented_at,
        "updated_at": now.isoformat()
    })
    await session.commit()

    logger.info(f"Action completed: rec {recommendation_id} step {step}")

    return {"success": True, "message": f"Step {step} completed"}


@router.post("/{recommendation_id}/dismiss")
async def dismiss_recommendation(
    recommendation_id: str,
    reason: Optional[str] = None,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Dismiss a recommendation."""
    await _ensure_recommendations_table(session)

    rec = await _get_recommendation_by_id(recommendation_id, session)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found"
        )

    if not _can_modify_recommendation(context, rec):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    now = datetime.utcnow()
    update_query = text("""
        UPDATE recommendations
        SET status = :status, updated_at = :updated_at
        WHERE recommendation_id = :recommendation_id
    """)
    await session.execute(update_query, {
        "recommendation_id": recommendation_id,
        "status": RecommendationStatus.DISMISSED.value,
        "updated_at": now.isoformat()
    })
    await session.commit()

    logger.info(f"Recommendation dismissed: {recommendation_id}, reason: {reason}")

    return {"success": True, "message": "Recommendation dismissed"}


# =============================================================================
# AI GENERATION
# =============================================================================

@router.post("/generate")
async def generate_recommendations(
    tax_return_id: Optional[str] = None,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Generate AI-powered tax recommendations.

    Analyzes user's tax situation and generates personalized recommendations.
    """
    await _ensure_recommendations_table(session)

    # In production, this would use AI/ML to analyze tax data
    # For now, return a message about the feature

    return {
        "success": True,
        "message": "Recommendation generation initiated",
        "status": "processing",
        "estimated_time_seconds": 30,
        "note": "In production, this would trigger AI analysis of tax data"
    }


# =============================================================================
# ANALYTICS
# =============================================================================

@router.get("/analytics/summary")
async def get_recommendation_analytics(
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Get recommendation analytics."""
    await _ensure_recommendations_table(session)

    # Build access conditions
    access_conditions, access_params = await _build_access_conditions(context)

    # Get counts by status
    status_query = text(f"""
        SELECT status, COUNT(*) as count
        FROM recommendations r
        WHERE {access_conditions}
        GROUP BY status
    """)
    status_result = await session.execute(status_query, access_params)
    status_rows = status_result.fetchall()
    by_status = {row[0]: row[1] for row in status_rows}

    # Get counts by category
    category_query = text(f"""
        SELECT category, COUNT(*) as count
        FROM recommendations r
        WHERE {access_conditions}
        GROUP BY category
    """)
    category_result = await session.execute(category_query, access_params)
    category_rows = category_result.fetchall()
    by_category = {row[0]: row[1] for row in category_rows}

    # Get total and savings aggregates
    totals_query = text(f"""
        SELECT
            COUNT(*) as total,
            COALESCE(SUM(estimated_savings_low), 0) as total_low,
            COALESCE(SUM(estimated_savings_high), 0) as total_high,
            COALESCE(SUM(CASE WHEN status = 'implemented'
                THEN (estimated_savings_low + estimated_savings_high) / 2
                ELSE 0 END), 0) as implemented_savings
        FROM recommendations r
        WHERE {access_conditions}
    """)
    totals_result = await session.execute(totals_query, access_params)
    totals_row = totals_result.fetchone()

    total_recommendations = totals_row[0] if totals_row else 0
    total_potential_savings_low = float(totals_row[1]) if totals_row else 0
    total_potential_savings_high = float(totals_row[2]) if totals_row else 0
    implemented_savings = float(totals_row[3]) if totals_row else 0

    return {
        "total_recommendations": total_recommendations,
        "by_status": by_status,
        "by_category": by_category,
        "total_potential_savings_low": total_potential_savings_low,
        "total_potential_savings_high": total_potential_savings_high,
        "implemented_savings": implemented_savings
    }
