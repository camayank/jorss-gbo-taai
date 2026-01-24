"""
Web Helpers - Reusable utilities for API endpoints.

Contains:
- Pagination helpers
- Response builders
- Validators
- Conversation history management
- Standardized error responses
"""

from .pagination import PaginationMeta, PaginatedResponse, paginate

# Conversation history management
try:
    from .conversation_history import (
        ConversationManager,
        prune_conversation_history,
        get_optimized_context,
        count_turns,
        should_summarize,
        SLIDING_WINDOW_SIZE,
    )
    _HISTORY_EXPORTS = [
        "ConversationManager",
        "prune_conversation_history",
        "get_optimized_context",
        "count_turns",
        "should_summarize",
        "SLIDING_WINDOW_SIZE",
    ]
except ImportError:
    _HISTORY_EXPORTS = []

# Standardized error responses
try:
    from .error_responses import (
        ErrorCode,
        StandardErrorResponse,
        create_error_response,
        raise_api_error,
        not_found_error,
        server_error,
        handle_validation_error,
        LoadingState,
        create_loading_response,
    )
    _ERROR_EXPORTS = [
        "ErrorCode",
        "StandardErrorResponse",
        "create_error_response",
        "raise_api_error",
        "not_found_error",
        "server_error",
        "handle_validation_error",
        "LoadingState",
        "create_loading_response",
    ]
except ImportError:
    _ERROR_EXPORTS = []

__all__ = [
    "PaginationMeta",
    "PaginatedResponse",
    "paginate",
] + _HISTORY_EXPORTS + _ERROR_EXPORTS
