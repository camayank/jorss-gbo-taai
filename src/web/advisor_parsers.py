"""
Parser and intent detection for the Intelligent Tax Advisor.

Re-exports parser functions from intelligent_advisor_api.py
for use by external modules. This module provides a clean import
path while the full extraction is completed incrementally.

Usage:
    from web.advisor_parsers import parse_user_message, EnhancedParser, detect_user_intent
"""

# Re-export parser functions from the main module.
# These have zero dependency on IntelligentChatEngine and are
# safe to import independently.
from web.intelligent_advisor_api import (
    parse_user_message,
    enhanced_parse_user_message,
    EnhancedParser,
    ConversationContext,
    detect_user_intent,
)

__all__ = [
    "parse_user_message",
    "enhanced_parse_user_message",
    "EnhancedParser",
    "ConversationContext",
    "detect_user_intent",
]
