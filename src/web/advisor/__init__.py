"""
Intelligent Tax Advisor Package.

Decomposed from the monolithic intelligent_advisor_api.py into:
- models.py: Pydantic request/response models
- parsers.py: Message parsing and intent detection
- report_routes.py: Safety check, PDF generation, universal report endpoints
"""

# Re-export models
from web.advisor.models import (  # noqa: F401
    FilingStatus,
    ChatMessage,
    TaxProfileInput,
    ChatRequest,
    StrategyRecommendation,
    TaxCalculationResult,
    ChatResponse,
    FullAnalysisRequest,
    FullAnalysisResponse,
)

# Re-export parsers
from web.advisor.parsers import (  # noqa: F401
    parse_user_message,
    enhanced_parse_user_message,
    EnhancedParser,
    ConversationContext,
    detect_user_intent,
)

# Re-export key items from the main module (chat engine, router)
try:
    from web.intelligent_advisor_api import (  # noqa: F401
        router,
        IntelligentChatEngine,
        convert_profile_to_tax_return,
    )
except ImportError:
    pass


def register_intelligent_advisor_routes(app):
    """Register advisor routes with the app."""
    try:
        from web.intelligent_advisor_api import router as _router
        app.include_router(_router)
    except ImportError:
        pass
