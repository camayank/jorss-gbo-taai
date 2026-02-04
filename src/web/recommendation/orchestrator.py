"""
Recommendation Orchestrator - Main Entry Point

SPEC-006: Orchestrates all recommendation generators and handles deduplication.
"""

import time
import logging
from typing import Dict, Any, List, Optional

from .models import UnifiedRecommendation, RecommendationResult
from .utils import validate_profile, get_urgency_info, get_lead_score

logger = logging.getLogger(__name__)


# =============================================================================
# RECOMMENDATION GENERATOR REGISTRY
# =============================================================================

# Import generators (lazy loading supported)
_generators_loaded = False
_generators = {}


def _load_generators():
    """Lazy load all recommendation generators."""
    global _generators_loaded, _generators

    if _generators_loaded:
        return

    # Core generators
    try:
        from .generators.core import (
            get_credit_optimizer_recs,
            get_deduction_analyzer_recs,
            get_investment_optimizer_recs,
        )
        _generators["credit_optimizer"] = get_credit_optimizer_recs
        _generators["deduction_analyzer"] = get_deduction_analyzer_recs
        _generators["investment_optimizer"] = get_investment_optimizer_recs
    except ImportError as e:
        logger.warning(f"Could not load core generators: {e}")

    # Retirement generators
    try:
        from .generators.retirement import (
            get_retirement_optimizer_recs,
            get_backdoor_roth_recs,
            get_medicare_irmaa_recs,
            get_social_security_recs,
        )
        _generators["retirement_optimizer"] = get_retirement_optimizer_recs
        _generators["backdoor_roth"] = get_backdoor_roth_recs
        _generators["medicare_irmaa"] = get_medicare_irmaa_recs
        _generators["social_security"] = get_social_security_recs
    except ImportError as e:
        logger.warning(f"Could not load retirement generators: {e}")

    # Credits generators
    try:
        from .generators.credits import get_education_savings_recs
        _generators["education_savings"] = get_education_savings_recs
    except ImportError as e:
        logger.warning(f"Could not load credits generators: {e}")

    # Deductions generators
    try:
        from .generators.deductions import (
            get_qbi_optimizer_recs,
            get_smart_deduction_detector_recs,
        )
        _generators["qbi_optimizer"] = get_qbi_optimizer_recs
        _generators["smart_deductions"] = get_smart_deduction_detector_recs
    except ImportError as e:
        logger.warning(f"Could not load deductions generators: {e}")

    # Investments generators
    try:
        from .generators.investments import get_opportunity_detector_recs
        _generators["opportunity_detector"] = get_opportunity_detector_recs
    except ImportError as e:
        logger.warning(f"Could not load investments generators: {e}")

    # Real estate generators
    try:
        from .generators.real_estate import (
            get_home_sale_exclusion_recs,
            get_1031_exchange_recs,
            get_installment_sale_recs,
            get_passive_activity_loss_recs,
            get_rental_depreciation_recs,
        )
        _generators["home_sale"] = get_home_sale_exclusion_recs
        _generators["1031_exchange"] = get_1031_exchange_recs
        _generators["installment_sale"] = get_installment_sale_recs
        _generators["passive_activity_loss"] = get_passive_activity_loss_recs
        _generators["rental_depreciation"] = get_rental_depreciation_recs
    except ImportError as e:
        logger.warning(f"Could not load real estate generators: {e}")

    # Lifecycle generators
    try:
        from .generators.lifecycle import (
            get_filing_status_optimizer_recs,
            get_timing_strategy_recs,
            get_charitable_strategy_recs,
        )
        _generators["filing_status"] = get_filing_status_optimizer_recs
        _generators["timing_strategy"] = get_timing_strategy_recs
        _generators["charitable_strategy"] = get_charitable_strategy_recs
    except ImportError as e:
        logger.warning(f"Could not load lifecycle generators: {e}")

    # Penalties generators
    try:
        from .generators.penalties import (
            get_amt_risk_recs,
            get_estimated_tax_penalty_recs,
        )
        _generators["amt_risk"] = get_amt_risk_recs
        _generators["estimated_tax_penalty"] = get_estimated_tax_penalty_recs
    except ImportError as e:
        logger.warning(f"Could not load penalties generators: {e}")

    # Entity generators
    try:
        from .generators.entity import (
            get_entity_optimizer_recs,
            get_cpa_opportunities,
        )
        _generators["entity_optimizer"] = get_entity_optimizer_recs
        _generators["cpa_opportunities"] = get_cpa_opportunities
    except ImportError as e:
        logger.warning(f"Could not load entity generators: {e}")

    # International generators
    try:
        from .generators.international import get_foreign_tax_credit_recs
        _generators["foreign_tax_credit"] = get_foreign_tax_credit_recs
    except ImportError as e:
        logger.warning(f"Could not load international generators: {e}")

    # Strategy generators
    try:
        from .generators.strategy import (
            get_withholding_optimizer_recs,
            get_tax_impact_recs,
            get_refund_estimator_recs,
            get_tax_strategy_advisor_recs,
            get_planning_insights_recs,
        )
        _generators["withholding_optimizer"] = get_withholding_optimizer_recs
        _generators["tax_impact"] = get_tax_impact_recs
        _generators["refund_estimator"] = get_refund_estimator_recs
        _generators["tax_strategy_advisor"] = get_tax_strategy_advisor_recs
        _generators["planning_insights"] = get_planning_insights_recs
    except ImportError as e:
        logger.warning(f"Could not load strategy generators: {e}")

    # Analytics generators
    try:
        from .generators.analytics import (
            get_tax_drivers_recs,
            get_complexity_router_recs,
            get_rules_based_recs,
            get_realtime_estimator_recs,
            get_cpa_knowledge_recs,
            get_adaptive_question_recs,
        )
        _generators["tax_drivers"] = get_tax_drivers_recs
        _generators["complexity_router"] = get_complexity_router_recs
        _generators["rules_based"] = get_rules_based_recs
        _generators["realtime_estimator"] = get_realtime_estimator_recs
        _generators["cpa_knowledge"] = get_cpa_knowledge_recs
        _generators["adaptive_questions"] = get_adaptive_question_recs
    except ImportError as e:
        logger.warning(f"Could not load analytics generators: {e}")

    _generators_loaded = True


# =============================================================================
# DEDUPLICATION LOGIC
# =============================================================================

def _normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    import re
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _get_dedup_key(rec: UnifiedRecommendation) -> str:
    """Generate a deduplication key for a recommendation."""
    return f"{rec.category}:{_normalize_text(rec.title)[:50]}"


def _are_similar_recommendations(rec1: UnifiedRecommendation, rec2: UnifiedRecommendation) -> bool:
    """Check if two recommendations are similar enough to merge."""
    if rec1.category != rec2.category:
        return False

    # Normalize titles
    title1 = _normalize_text(rec1.title)
    title2 = _normalize_text(rec2.title)

    # Check title similarity
    if title1 == title2:
        return True

    # Check for significant word overlap
    words1 = set(title1.split())
    words2 = set(title2.split())

    if len(words1) == 0 or len(words2) == 0:
        return False

    overlap = len(words1 & words2)
    similarity = overlap / min(len(words1), len(words2))

    return similarity > 0.6


def _merge_recommendations(recs: List[UnifiedRecommendation]) -> UnifiedRecommendation:
    """Merge similar recommendations into one."""
    if len(recs) == 1:
        return recs[0]

    # Take the one with highest savings and best confidence
    best = max(recs, key=lambda r: (r.potential_savings, r.confidence))

    # Merge action items and requirements
    all_actions = []
    all_requirements = []
    all_warnings = []

    for rec in recs:
        for item in rec.action_items:
            if item not in all_actions:
                all_actions.append(item)
        for item in rec.requirements:
            if item not in all_requirements:
                all_requirements.append(item)
        for item in rec.warnings:
            if item not in all_warnings:
                all_warnings.append(item)

    # Create merged recommendation
    return UnifiedRecommendation(
        title=best.title,
        description=best.description,
        potential_savings=max(r.potential_savings for r in recs),
        priority=best.priority,
        category=best.category,
        confidence=best.confidence,
        complexity=best.complexity,
        action_items=all_actions[:5],  # Limit
        requirements=all_requirements[:3],
        warnings=all_warnings[:3],
        source=", ".join(set(r.source for r in recs)),
        metadata={"merged_from": len(recs)},
    )


def _deduplicate_recommendations(recs: List[UnifiedRecommendation]) -> List[UnifiedRecommendation]:
    """Remove duplicate and similar recommendations."""
    if not recs:
        return []

    # Group by dedup key
    groups: Dict[str, List[UnifiedRecommendation]] = {}
    for rec in recs:
        key = _get_dedup_key(rec)
        if key not in groups:
            groups[key] = []
        groups[key].append(rec)

    # Merge groups
    deduped = []
    for group in groups.values():
        merged = _merge_recommendations(group)
        deduped.append(merged)

    # Second pass: check for similar recommendations across groups
    final = []
    used = set()

    for i, rec in enumerate(deduped):
        if i in used:
            continue

        similar_group = [rec]
        for j in range(i + 1, len(deduped)):
            if j not in used and _are_similar_recommendations(rec, deduped[j]):
                similar_group.append(deduped[j])
                used.add(j)

        final.append(_merge_recommendations(similar_group))

    return final


def _sort_recommendations(
    recs: List[UnifiedRecommendation],
    urgency_level: str = "normal"
) -> List[UnifiedRecommendation]:
    """Sort recommendations by priority and savings."""
    priority_order = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
    }

    def sort_key(rec: UnifiedRecommendation):
        # Boost critical items during urgent periods
        priority_boost = 0
        if urgency_level == "high" and rec.priority == "critical":
            priority_boost = -1

        return (
            priority_order.get(rec.priority, 2) + priority_boost,
            -rec.potential_savings,
            -rec.confidence,
        )

    return sorted(recs, key=sort_key)


# =============================================================================
# MAIN ORCHESTRATION
# =============================================================================

async def get_recommendations(
    profile: Dict[str, Any],
    generators: Optional[List[str]] = None,
    max_recommendations: int = 20,
    include_low_priority: bool = True,
) -> RecommendationResult:
    """
    Generate tax optimization recommendations.

    This is the main entry point for the recommendation engine.

    Args:
        profile: Tax profile data
        generators: Optional list of specific generators to use
        max_recommendations: Maximum recommendations to return
        include_low_priority: Whether to include low priority items

    Returns:
        RecommendationResult with recommendations and metadata
    """
    start_time = time.time()

    result = RecommendationResult()

    # Validate and normalize profile
    validated_profile = validate_profile(profile)

    # Get urgency info
    urgency_level, deadline_info = get_urgency_info()
    result.urgency_level = urgency_level
    result.deadline_info = deadline_info

    # Calculate lead score
    result.lead_score = get_lead_score(validated_profile)

    # Build profile summary
    result.profile_summary = {
        "filing_status": validated_profile.get("filing_status"),
        "agi": validated_profile.get("agi", 0),
        "has_dependents": validated_profile.get("has_dependents", False),
        "is_self_employed": validated_profile.get("is_self_employed", False),
    }

    # Load generators
    _load_generators()

    # Determine which generators to run
    if generators:
        generators_to_run = {k: v for k, v in _generators.items() if k in generators}
    else:
        generators_to_run = _generators

    # Run all generators
    all_recs = []
    for name, generator_fn in generators_to_run.items():
        try:
            recs = generator_fn(validated_profile)
            all_recs.extend(recs)
            result.sources_used.append(name)
        except Exception as e:
            logger.error(f"Generator {name} failed: {e}")
            result.errors.append(f"{name}: {str(e)}")

    # Deduplicate
    deduped_recs = _deduplicate_recommendations(all_recs)

    # Filter low priority if needed
    if not include_low_priority:
        deduped_recs = [r for r in deduped_recs if r.priority != "low"]

    # Sort
    sorted_recs = _sort_recommendations(deduped_recs, urgency_level)

    # Limit
    result.recommendations = sorted_recs[:max_recommendations]

    # Calculate totals
    result.total_potential_savings = sum(r.potential_savings for r in result.recommendations)

    # Record processing time
    result.processing_time_ms = (time.time() - start_time) * 1000

    return result


def get_recommendations_sync(
    profile: Dict[str, Any],
    generators: Optional[List[str]] = None,
    max_recommendations: int = 20,
) -> RecommendationResult:
    """
    Synchronous wrapper for get_recommendations.

    For backwards compatibility with sync code.
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Can't use asyncio.run() in running loop
            # Create task and wait
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    get_recommendations(profile, generators, max_recommendations)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                get_recommendations(profile, generators, max_recommendations)
            )
    except RuntimeError:
        # No event loop
        return asyncio.run(
            get_recommendations(profile, generators, max_recommendations)
        )
