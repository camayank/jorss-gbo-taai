"""
Intelligent Tax Advisor Package.

This package provides the intelligent tax advisory chatbot backend.
Currently re-exports from the monolithic intelligent_advisor_api.py.

Future work: Decompose intelligent_advisor_api.py into:
- models.py: Pydantic request/response models
- chat_engine.py: IntelligentChatEngine class
- parsers.py: Message parsing and intent detection
- converters.py: Profile/tax return conversion
- routes.py: API route handlers
"""

# Re-export from the monolithic module for now
try:
    from web.intelligent_advisor_api import (
        router,
        IntelligentChatEngine,
        parse_user_message,
        enhanced_parse_user_message,
        convert_profile_to_tax_return,
    )
except ImportError:
    pass

# Registration function
def register_intelligent_advisor_routes(app):
    """Register advisor routes with the app."""
    try:
        from web.intelligent_advisor_api import router as _router
        app.include_router(_router)
    except ImportError:
        pass
