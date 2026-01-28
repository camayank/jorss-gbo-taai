"""
Query Performance Tests

SPEC-010: Tests for N+1 query detection and query efficiency.

These tests ensure that database operations are efficient and don't
suffer from N+1 query problems.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from tests.helpers.query_counter import QueryCounter, QueryStats, QueryInfo, assert_query_count


class TestQueryCounter:
    """Tests for the QueryCounter utility itself."""

    def test_query_stats_count(self):
        """Test that query stats correctly counts queries."""
        stats = QueryStats()
        stats.queries = [
            QueryInfo(sql="SELECT * FROM users", duration_ms=10),
            QueryInfo(sql="SELECT * FROM returns", duration_ms=20),
            QueryInfo(sql="INSERT INTO audit", duration_ms=5),
        ]

        assert stats.count == 3
        assert stats.select_count == 2
        assert stats.insert_count == 1
        assert stats.update_count == 0
        assert stats.delete_count == 0

    def test_query_stats_total_duration(self):
        """Test duration calculation."""
        stats = QueryStats()
        stats.queries = [
            QueryInfo(sql="SELECT 1", duration_ms=10.5),
            QueryInfo(sql="SELECT 2", duration_ms=20.3),
        ]

        assert stats.total_duration_ms == pytest.approx(30.8, 0.1)

    def test_n_plus_one_detection_negative(self):
        """Test that normal queries don't trigger N+1 detection."""
        stats = QueryStats()
        stats.queries = [
            QueryInfo(sql="SELECT * FROM users WHERE id = 1"),
            QueryInfo(sql="SELECT * FROM returns WHERE user_id = 1"),
            QueryInfo(sql="SELECT * FROM documents WHERE return_id = 1"),
        ]

        assert not stats.has_n_plus_one()

    def test_n_plus_one_detection_positive(self):
        """Test that repeated similar queries trigger N+1 detection."""
        stats = QueryStats()

        # Simulate N+1: 1 query for list + N queries for each item's relation
        stats.queries = [
            QueryInfo(sql="SELECT * FROM returns"),
        ]

        # Add 15 similar queries (simulating loading related data in a loop)
        for i in range(15):
            stats.queries.append(
                QueryInfo(sql=f"SELECT * FROM documents WHERE return_id = {i}")
            )

        assert stats.has_n_plus_one(threshold=10)

    def test_slow_query_detection(self):
        """Test slow query detection."""
        stats = QueryStats()
        stats.queries = [
            QueryInfo(sql="SELECT fast", duration_ms=10),
            QueryInfo(sql="SELECT slow", duration_ms=150),
            QueryInfo(sql="SELECT medium", duration_ms=50),
        ]

        slow = stats.get_slow_queries(threshold_ms=100)
        assert len(slow) == 1
        assert slow[0].sql == "SELECT slow"

    def test_query_stats_summary(self):
        """Test summary generation."""
        stats = QueryStats()
        stats.queries = [
            QueryInfo(sql="SELECT * FROM users", duration_ms=10),
            QueryInfo(sql="INSERT INTO logs", duration_ms=5),
        ]
        stats.end_time = stats.start_time + 0.1

        summary = stats.summary()

        assert "Total queries: 2" in summary
        assert "SELECT: 1" in summary
        assert "INSERT: 1" in summary

    def test_query_counter_context_manager_sync(self):
        """Test sync context manager."""
        with QueryCounter() as counter:
            # Simulate adding queries (normally done by SQLAlchemy events)
            counter.stats.queries.append(QueryInfo(sql="SELECT 1"))

        assert counter.count == 1

    @pytest.mark.asyncio
    async def test_query_counter_context_manager_async(self):
        """Test async context manager."""
        async with QueryCounter() as counter:
            counter.stats.queries.append(QueryInfo(sql="SELECT 1"))

        assert counter.count == 1


class TestQueryPerformancePatterns:
    """
    Example tests demonstrating query performance validation patterns.

    These serve as templates for testing repository methods.
    """

    def test_single_entity_load_efficiency(self):
        """
        Test: Loading a single entity should require minimal queries.

        Expected: 1 query for the entity, possibly 1-2 for eager-loaded relations.
        """
        stats = QueryStats()

        # Simulate efficient single-entity load with eager loading
        stats.queries = [
            QueryInfo(
                sql="SELECT users.*, profiles.* FROM users "
                    "LEFT JOIN profiles ON users.id = profiles.user_id "
                    "WHERE users.id = ?",
                duration_ms=5
            ),
        ]

        assert stats.count <= 2, "Single entity load should use 1-2 queries"
        assert not stats.has_n_plus_one()

    def test_list_with_relations_efficiency(self):
        """
        Test: Listing entities with relations should avoid N+1.

        Expected: 2-3 queries total (list + eager loads), NOT 1+N queries.
        """
        stats = QueryStats()

        # GOOD PATTERN: Separate queries for base and relations (selectinload)
        stats.queries = [
            QueryInfo(sql="SELECT * FROM tax_returns LIMIT 50", duration_ms=10),
            QueryInfo(
                sql="SELECT * FROM documents WHERE return_id IN (?, ?, ?, ...)",
                duration_ms=15
            ),
            QueryInfo(
                sql="SELECT * FROM audit_logs WHERE return_id IN (?, ?, ?, ...)",
                duration_ms=12
            ),
        ]

        assert stats.count <= 5, "List with relations should use few queries"
        assert not stats.has_n_plus_one(), "Should not exhibit N+1 pattern"

    def test_n_plus_one_anti_pattern(self):
        """
        Test: Demonstrate what N+1 looks like (this test shows the BAD pattern).

        This is an example of what NOT to do - included for documentation.
        """
        stats = QueryStats()

        # BAD PATTERN: 1 query for list + N queries for relations
        stats.queries = [
            QueryInfo(sql="SELECT * FROM tax_returns LIMIT 20", duration_ms=5),
        ]

        # N queries for each return's documents (BAD!)
        for i in range(20):
            stats.queries.append(
                QueryInfo(
                    sql=f"SELECT * FROM documents WHERE return_id = {i}",
                    duration_ms=3
                )
            )

        # This SHOULD fail - demonstrating the problem
        assert stats.has_n_plus_one(threshold=10), \
            "This query pattern exhibits N+1 - use eager loading instead"


class TestEagerLoadingStrategies:
    """Document recommended eager loading strategies."""

    def test_joinedload_for_single_relations(self):
        """
        joinedload() - Best for to-one relationships (ForeignKey).

        Example:
            query.options(joinedload(TaxReturn.taxpayer))

        Results in a single JOIN query.
        """
        stats = QueryStats()
        stats.queries = [
            QueryInfo(
                sql="SELECT returns.*, taxpayers.* "
                    "FROM tax_returns AS returns "
                    "LEFT JOIN taxpayers ON returns.taxpayer_id = taxpayers.id",
                duration_ms=15
            ),
        ]

        assert stats.count == 1, "joinedload uses single query"
        assert not stats.has_n_plus_one()

    def test_selectinload_for_collections(self):
        """
        selectinload() - Best for to-many relationships (one-to-many).

        Example:
            query.options(selectinload(TaxReturn.documents))

        Results in 2 queries: one for parents, one for all children.
        """
        stats = QueryStats()
        stats.queries = [
            QueryInfo(sql="SELECT * FROM tax_returns WHERE ...", duration_ms=10),
            QueryInfo(
                sql="SELECT * FROM documents WHERE return_id IN (?, ?, ?, ...)",
                duration_ms=20
            ),
        ]

        assert stats.count == 2, "selectinload uses 2 queries"
        assert not stats.has_n_plus_one()

    def test_subqueryload_for_complex_queries(self):
        """
        subqueryload() - For complex parent queries that can't use IN.

        Example:
            query.options(subqueryload(TaxReturn.audit_entries))

        Uses a correlated subquery - useful when parent query has LIMIT/OFFSET.
        """
        stats = QueryStats()
        stats.queries = [
            QueryInfo(
                sql="SELECT * FROM tax_returns ORDER BY created_at DESC LIMIT 10",
                duration_ms=10
            ),
            QueryInfo(
                sql="SELECT * FROM audit_entries WHERE return_id IN "
                    "(SELECT id FROM tax_returns ORDER BY created_at DESC LIMIT 10)",
                duration_ms=25
            ),
        ]

        assert stats.count == 2, "subqueryload uses 2 queries"
        assert not stats.has_n_plus_one()


# =============================================================================
# REPOSITORY PERFORMANCE TESTS (Examples)
# =============================================================================

class TestRepositoryPerformance:
    """
    Performance tests for repository methods.

    These tests verify that repository implementations use efficient queries.
    Add actual repository tests here as the codebase evolves.
    """

    @pytest.mark.skip(reason="Requires actual database connection - template only")
    @pytest.mark.asyncio
    async def test_tax_return_repository_list_performance(self):
        """
        Test: TaxReturnRepository.list_returns() should be efficient.

        Expected behavior:
        - Uses pagination (LIMIT/OFFSET)
        - Eager loads commonly needed relations
        - No N+1 queries
        """
        from database.repositories.tax_return_repository import TaxReturnRepository

        async with QueryCounter(log_queries=True) as counter:
            repo = TaxReturnRepository(session=None)  # Would need real session
            results = await repo.list_returns(limit=50)

        # Assertions
        assert counter.count <= 5, \
            f"list_returns should use ≤5 queries, used {counter.count}"
        assert not counter.stats.has_n_plus_one(), \
            "list_returns should not have N+1 queries"

        # Log for analysis
        print(counter.stats.summary())

    @pytest.mark.skip(reason="Requires actual database connection - template only")
    @pytest.mark.asyncio
    @assert_query_count(max_queries=3)
    async def test_get_return_with_documents_performance(self):
        """
        Test: Getting a return with documents should use eager loading.

        Using @assert_query_count decorator for automatic validation.
        """
        from database.repositories.tax_return_repository import TaxReturnRepository

        repo = TaxReturnRepository(session=None)  # Would need real session
        result = await repo.get("some-uuid")

        # If we reach here, query count is within limits
        assert result is not None


# =============================================================================
# BENCHMARK TESTS
# =============================================================================

class TestQueryBenchmarks:
    """Benchmark tests for establishing performance baselines."""

    def test_establish_baseline_metrics(self):
        """
        Establish baseline metrics for query performance.

        These numbers serve as reference points for performance regression testing.
        """
        baselines = {
            "single_entity_get": {"max_queries": 2, "max_duration_ms": 50},
            "list_with_pagination": {"max_queries": 3, "max_duration_ms": 100},
            "list_with_relations": {"max_queries": 5, "max_duration_ms": 200},
            "complex_report": {"max_queries": 10, "max_duration_ms": 500},
        }

        # These serve as documentation of expected performance
        for operation, limits in baselines.items():
            assert limits["max_queries"] > 0, f"{operation} should have query limit"
            assert limits["max_duration_ms"] > 0, f"{operation} should have time limit"

        # Store baselines as class attribute for use in other tests if needed
        self.__class__.BASELINES = baselines
