"""
Feature Access API

Endpoints for checking feature availability and access control.
Used by frontend to show/hide features dynamically.
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any, List
from pydantic import BaseModel

from ..rbac.dependencies import require_auth, AuthContext
from ..rbac.feature_access_control import (
    Features,
    Feature,
    FeatureCategory,
    check_feature_access,
    get_user_features,
    get_features_by_category
)

router = APIRouter(prefix="/api/features", tags=["feature-access"])


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class FeatureAccessResponse(BaseModel):
    """Feature access information"""
    code: str
    name: str
    description: str
    category: str
    icon: str
    color: str
    allowed: bool
    reason: str = ""
    upgrade_tier: str = None
    upgrade_message: str = ""


class UserFeaturesResponse(BaseModel):
    """All features for a user"""
    features: Dict[str, FeatureAccessResponse]
    categories: Dict[str, List[Dict[str, Any]]]
    total_features: int
    allowed_features: int


class CheckFeatureRequest(BaseModel):
    """Request to check specific feature"""
    feature_code: str


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/my-features", response_model=UserFeaturesResponse)
async def get_my_features(ctx: AuthContext = Depends(require_auth)):
    """
    Get all features and their availability for the current user.

    Returns complete feature catalog with access status for each feature.
    Frontend uses this to show/hide features dynamically.
    """
    features_dict = get_user_features(ctx)

    # Convert to response models
    features_response = {
        code: FeatureAccessResponse(
            code=code,
            name=info["name"],
            description=info["description"],
            category=info["category"],
            icon=info["icon"],
            color=info["color"],
            allowed=info["allowed"],
            reason=info.get("reason", ""),
            upgrade_tier=info.get("upgrade_tier"),
            upgrade_message=info.get("upgrade_message", "")
        )
        for code, info in features_dict.items()
    }

    # Group by category
    categories_response = {
        cat.value: get_features_by_category(ctx, cat)
        for cat in FeatureCategory
    }

    # Count allowed features
    allowed_count = sum(1 for info in features_dict.values() if info["allowed"])

    return UserFeaturesResponse(
        features=features_response,
        categories=categories_response,
        total_features=len(features_dict),
        allowed_features=allowed_count
    )


@router.post("/check")
async def check_feature(
    request: CheckFeatureRequest,
    ctx: AuthContext = Depends(require_auth)
):
    """
    Check if user has access to a specific feature.

    Returns detailed access information including reason if denied.
    """
    # Find feature by code
    feature = None
    for attr in dir(Features):
        obj = getattr(Features, attr)
        if isinstance(obj, Feature) and obj.code == request.feature_code:
            feature = obj
            break

    if not feature:
        return {
            "allowed": False,
            "reason": f"Unknown feature: {request.feature_code}"
        }

    # Check access
    access = check_feature_access(feature, ctx)

    return {
        "feature_code": feature.code,
        "feature_name": feature.name,
        "allowed": access["allowed"],
        "reason": access.get("reason", ""),
        "upgrade_tier": access.get("upgrade_tier"),
        "upgrade_message": feature.upgrade_message if not access["allowed"] else "",
        "current_tier": ctx.tenant_id  # Could fetch actual tier
    }


@router.get("/category/{category}")
async def get_features_by_category_endpoint(
    category: str,
    ctx: AuthContext = Depends(require_auth)
):
    """
    Get all features in a specific category.

    Useful for building category-specific UI (e.g., "AI Features" section).
    """
    try:
        cat_enum = FeatureCategory(category)
    except ValueError:
        return {
            "error": f"Unknown category: {category}",
            "available_categories": [c.value for c in FeatureCategory]
        }

    features = get_features_by_category(ctx, cat_enum)

    return {
        "category": category,
        "features": features,
        "total": len(features),
        "allowed": sum(1 for f in features if f["allowed"])
    }


@router.get("/available")
async def get_available_features(ctx: AuthContext = Depends(require_auth)):
    """
    Get only features that are available to the user.

    Returns minimal list of enabled features for quick checks.
    """
    all_features = get_user_features(ctx)

    available = [
        {
            "code": code,
            "name": info["name"],
            "icon": info["icon"],
            "category": info["category"]
        }
        for code, info in all_features.items()
        if info["allowed"]
    ]

    return {
        "features": available,
        "count": len(available)
    }


@router.get("/locked")
async def get_locked_features(ctx: AuthContext = Depends(require_auth)):
    """
    Get features that are locked for the user.

    Returns features that require upgrade or additional permissions.
    Useful for showing upgrade prompts.
    """
    all_features = get_user_features(ctx)

    locked = [
        {
            "code": code,
            "name": info["name"],
            "icon": info["icon"],
            "category": info["category"],
            "reason": info["reason"],
            "upgrade_tier": info.get("upgrade_tier"),
            "upgrade_message": info["upgrade_message"]
        }
        for code, info in all_features.items()
        if not info["allowed"]
    ]

    return {
        "features": locked,
        "count": len(locked)
    }


@router.get("/catalog")
async def get_feature_catalog():
    """
    Get complete feature catalog (public endpoint).

    Shows all platform features for marketing/sales purposes.
    Does not require authentication.
    """
    all_features = [
        getattr(Features, attr) for attr in dir(Features)
        if isinstance(getattr(Features, attr), Feature)
    ]

    catalog = []
    for feature in all_features:
        catalog.append({
            "code": feature.code,
            "name": feature.name,
            "description": feature.description,
            "category": feature.category.value,
            "icon": feature.ui_icon,
            "color": feature.ui_color,
            "min_tier": feature.min_tier.value,
            "allowed_roles": list(feature.allowed_roles) if feature.allowed_roles else None
        })

    # Group by category
    by_category = {}
    for feature in catalog:
        cat = feature["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(feature)

    return {
        "features": catalog,
        "by_category": by_category,
        "total": len(catalog),
        "categories": list(by_category.keys())
    }
