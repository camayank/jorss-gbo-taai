"""
Conversation History Management - Sliding window and summarization utilities.

Provides:
- Sliding window to keep only recent conversation turns
- Summarization of older messages to preserve context
- Efficient memory management for long conversations

Resolves Audit Finding: "AI conversation history bloat"
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Configuration
SLIDING_WINDOW_SIZE = 15  # Keep last 15 turns (30 messages: 15 user + 15 assistant)
SUMMARIZE_AFTER_TURNS = 10  # Create summary after every 10 turns
MAX_SUMMARY_LENGTH = 500  # Max characters for summary


class ConversationManager:
    """
    Manages conversation history with sliding window and summarization.

    Keeps recent messages for immediate context while summarizing
    older messages to preserve important information without bloat.
    """

    def __init__(
        self,
        window_size: int = SLIDING_WINDOW_SIZE,
        summarize_after: int = SUMMARIZE_AFTER_TURNS,
    ):
        self.window_size = window_size
        self.summarize_after = summarize_after
        self._summaries: List[str] = []

    def prune_history(
        self,
        messages: List[Dict[str, Any]],
        preserve_system: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Prune conversation history to sliding window size.

        Args:
            messages: Full conversation history
            preserve_system: Keep system messages at start

        Returns:
            Pruned message list with recent messages
        """
        if len(messages) <= self.window_size * 2:
            return messages

        # Separate system messages from conversation
        system_messages = []
        conversation_messages = []

        for msg in messages:
            role = msg.get("role", "")
            if role == "system" and preserve_system:
                system_messages.append(msg)
            else:
                conversation_messages.append(msg)

        # Keep only recent conversation messages
        recent_count = self.window_size * 2  # user + assistant pairs
        recent_messages = conversation_messages[-recent_count:]

        # Log pruning
        pruned_count = len(conversation_messages) - len(recent_messages)
        if pruned_count > 0:
            logger.info(f"Pruned {pruned_count} old messages from conversation history")

        return system_messages + recent_messages

    def summarize_conversation(
        self,
        messages: List[Dict[str, Any]],
        include_extracted_data: bool = True,
    ) -> str:
        """
        Create a summary of the conversation for context preservation.

        Args:
            messages: Messages to summarize
            include_extracted_data: Include any extracted entities in summary

        Returns:
            Summary string
        """
        if not messages:
            return ""

        # Extract key information from messages
        topics_discussed = []
        data_collected = []
        user_preferences = []

        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")

            # Extract topics from assistant messages
            if role == "assistant":
                if any(word in content.lower() for word in ["income", "w-2", "wages", "salary"]):
                    topics_discussed.append("income")
                if any(word in content.lower() for word in ["deduction", "itemize", "standard"]):
                    topics_discussed.append("deductions")
                if any(word in content.lower() for word in ["credit", "child", "earned income"]):
                    topics_discussed.append("credits")
                if any(word in content.lower() for word in ["filing status", "single", "married"]):
                    topics_discussed.append("filing status")
                if any(word in content.lower() for word in ["refund", "owe", "tax liability"]):
                    topics_discussed.append("tax calculation")

            # Track user responses for context
            if role == "user":
                # Look for data mentions
                if "$" in content:
                    data_collected.append("monetary values mentioned")
                if any(word in content.lower() for word in ["yes", "no", "correct", "right"]):
                    user_preferences.append("confirmations given")

        # Build summary
        summary_parts = []

        unique_topics = list(set(topics_discussed))
        if unique_topics:
            summary_parts.append(f"Topics covered: {', '.join(unique_topics[:5])}")

        if data_collected:
            summary_parts.append(f"Data collected: {', '.join(set(data_collected)[:3])}")

        # Add message count
        user_msgs = sum(1 for m in messages if m.get("role") == "user")
        summary_parts.append(f"Conversation: {user_msgs} user messages")

        summary = ". ".join(summary_parts)

        # Truncate if needed
        if len(summary) > MAX_SUMMARY_LENGTH:
            summary = summary[:MAX_SUMMARY_LENGTH - 3] + "..."

        return summary

    def get_context_messages(
        self,
        messages: List[Dict[str, Any]],
        extracted_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get optimized messages for AI context.

        Returns pruned history with optional summary prepended.

        Args:
            messages: Full conversation history
            extracted_data: Optional extracted data to include in context

        Returns:
            Optimized message list for AI processing
        """
        # Check if summarization is needed
        if len(messages) > self.summarize_after * 2:
            # Get messages to summarize (older ones)
            split_point = len(messages) - (self.window_size * 2)
            old_messages = messages[:split_point]
            recent_messages = messages[split_point:]

            # Create summary of old messages
            summary = self.summarize_conversation(old_messages)

            if summary:
                # Create a system message with the summary
                context_message = {
                    "role": "system",
                    "content": f"Previous conversation summary: {summary}",
                    "timestamp": datetime.now().isoformat(),
                    "is_summary": True,
                }

                # Return summary + recent messages
                return [context_message] + recent_messages

        # No summarization needed, just prune
        return self.prune_history(messages)


def prune_conversation_history(
    messages: List[Dict[str, Any]],
    max_turns: int = SLIDING_WINDOW_SIZE,
) -> List[Dict[str, Any]]:
    """
    Simple function to prune conversation history.

    Convenience wrapper around ConversationManager.prune_history().

    Args:
        messages: List of conversation messages
        max_turns: Maximum number of turns to keep

    Returns:
        Pruned message list

    Example:
        >>> history = [{"role": "user", "content": "hi"}] * 100
        >>> pruned = prune_conversation_history(history, max_turns=10)
        >>> len(pruned)
        20
    """
    manager = ConversationManager(window_size=max_turns)
    return manager.prune_history(messages)


def get_optimized_context(
    messages: List[Dict[str, Any]],
    extracted_data: Optional[Dict[str, Any]] = None,
    max_turns: int = SLIDING_WINDOW_SIZE,
) -> List[Dict[str, Any]]:
    """
    Get optimized conversation context for AI processing.

    Prunes old messages and optionally adds summary.

    Args:
        messages: Full conversation history
        extracted_data: Optional extracted data for context
        max_turns: Maximum turns to keep

    Returns:
        Optimized message list
    """
    manager = ConversationManager(window_size=max_turns)
    return manager.get_context_messages(messages, extracted_data)


def count_turns(messages: List[Dict[str, Any]]) -> int:
    """
    Count conversation turns (user-assistant pairs).

    Args:
        messages: List of conversation messages

    Returns:
        Number of complete turns
    """
    user_count = sum(1 for m in messages if m.get("role") == "user")
    return user_count


def should_summarize(messages: List[Dict[str, Any]], threshold: int = SUMMARIZE_AFTER_TURNS) -> bool:
    """
    Check if conversation should be summarized.

    Args:
        messages: List of conversation messages
        threshold: Turn count threshold for summarization

    Returns:
        True if summarization is recommended
    """
    return count_turns(messages) > threshold
