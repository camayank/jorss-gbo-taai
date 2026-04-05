"""Tests for analytics materialized views refresh task."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from src.tasks.analytics_refresh import refresh_all_views, MATERIALIZED_VIEWS


class TestAnalyticsRefresh:
    """Test suite for analytics materialized view refresh."""

    @patch("src.tasks.analytics_refresh.get_db_session")
    def test_refresh_all_views_success(self, mock_session_class):
        """Test successful refresh of all materialized views."""
        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Call the task
        result = refresh_all_views()

        # Verify all views were attempted
        assert result["success"] is True
        assert len(result["views_refreshed"]) == len(MATERIALIZED_VIEWS)
        assert len(result["views_failed"]) == 0
        assert result["total_duration_seconds"] is not None

        # Verify session was closed
        mock_session.close.assert_called_once()

    @patch("src.tasks.analytics_refresh.emit_cloudwatch_alarm")
    @patch("src.tasks.analytics_refresh.get_db_session")
    def test_refresh_with_partial_failure(self, mock_session_class, mock_alarm):
        """Test refresh when some views fail."""
        # Setup mock session that fails on second view
        mock_session = MagicMock()
        mock_session.execute.side_effect = [
            None,  # First view succeeds
            Exception("Lock timeout"),  # Second view fails
            None,  # Third view succeeds
            None,  # Fourth view succeeds
            None,  # Fifth view succeeds
        ]
        mock_session_class.return_value = mock_session

        # Call the task
        result = refresh_all_views()

        # Verify partial success
        assert result["success"] is False
        assert len(result["views_refreshed"]) == 4
        assert len(result["views_failed"]) == 1
        assert result["views_failed"][0]["view"] == "analytics_document_metrics"

        # Verify alarm was emitted
        mock_alarm.assert_called_once()

    @patch("src.tasks.analytics_refresh.get_db_session")
    def test_refresh_views_order(self, mock_session_class):
        """Test that views are refreshed in correct order."""
        # Setup mock session
        mock_session = MagicMock()
        call_order = []

        def execute_side_effect(query):
            # Extract view name from query
            query_str = str(query)
            for view in MATERIALIZED_VIEWS:
                if view in query_str:
                    call_order.append(view)
                    break

        mock_session.execute.side_effect = execute_side_effect
        mock_session_class.return_value = mock_session

        # Call the task
        result = refresh_all_views()

        # Verify order matches MATERIALIZED_VIEWS list
        assert call_order == MATERIALIZED_VIEWS

    @patch("src.tasks.analytics_refresh.get_db_session")
    def test_refresh_session_cleanup_on_error(self, mock_session_class):
        """Test that session is properly closed even on error."""
        # Setup mock session that raises an exception
        mock_session = MagicMock()
        mock_session.execute.side_effect = Exception("Database connection error")
        mock_session_class.return_value = mock_session

        # Call the task and expect it to handle the error
        result = refresh_all_views()

        # Verify session was closed despite error
        mock_session.close.assert_called_once()
        assert result["success"] is False

    def test_materialized_views_list(self):
        """Test that all expected materialized views are in the refresh list."""
        expected_views = {
            "analytics_completion_metrics",
            "analytics_document_metrics",
            "analytics_advisor_activity",
            "analytics_review_metrics",
            "analytics_return_processing_stats",
        }
        assert set(MATERIALIZED_VIEWS) == expected_views

    @patch("src.tasks.analytics_refresh.get_db_session")
    def test_concurrent_refresh_query(self, mock_session_class):
        """Test that REFRESH MATERIALIZED VIEW CONCURRENTLY is used."""
        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Call the task
        refresh_all_views()

        # Verify CONCURRENTLY keyword was used in all queries
        for call in mock_session.execute.call_args_list:
            query = str(call[0][0])
            assert "REFRESH MATERIALIZED VIEW CONCURRENTLY" in query
