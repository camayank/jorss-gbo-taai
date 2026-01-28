"""
N+1 Query Detection Utilities

SPEC-010: Tools for detecting and preventing N+1 query patterns in tests.

Usage:
    from tests.utils.query_counter import QueryCounter, assert_query_count

    async def test_no_n_plus_one():
        async with QueryCounter() as counter:
            # Your database operations here
            results = await repository.list_with_relations()

        # Assert query count is within expected bounds
        assert counter.count <= 3, f"Too many queries: {counter.count}"

    # Or use the decorator
    @assert_query_count(max_queries=5)
    async def test_efficient_query():
        await repository.get_all_with_eager_load()
"""

import logging
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Any
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class QueryInfo:
    """Information about a single query execution."""
    sql: str
    parameters: Optional[dict] = None
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def __str__(self):
        params = f" | params={self.parameters}" if self.parameters else ""
        return f"[{self.duration_ms:.2f}ms] {self.sql[:200]}{params}"


@dataclass
class QueryStats:
    """Statistics about query execution."""
    queries: List[QueryInfo] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    @property
    def count(self) -> int:
        """Total number of queries executed."""
        return len(self.queries)

    @property
    def total_duration_ms(self) -> float:
        """Total duration of all queries in milliseconds."""
        return sum(q.duration_ms for q in self.queries)

    @property
    def elapsed_ms(self) -> float:
        """Total elapsed time including application code."""
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000

    @property
    def select_count(self) -> int:
        """Number of SELECT queries."""
        return sum(1 for q in self.queries if q.sql.strip().upper().startswith("SELECT"))

    @property
    def insert_count(self) -> int:
        """Number of INSERT queries."""
        return sum(1 for q in self.queries if q.sql.strip().upper().startswith("INSERT"))

    @property
    def update_count(self) -> int:
        """Number of UPDATE queries."""
        return sum(1 for q in self.queries if q.sql.strip().upper().startswith("UPDATE"))

    @property
    def delete_count(self) -> int:
        """Number of DELETE queries."""
        return sum(1 for q in self.queries if q.sql.strip().upper().startswith("DELETE"))

    def has_n_plus_one(self, threshold: int = 10) -> bool:
        """
        Detect potential N+1 query pattern.

        Returns True if there are many similar SELECT queries,
        which often indicates an N+1 problem.
        """
        if self.select_count < threshold:
            return False

        # Group queries by their structure (ignoring parameter values)
        query_patterns = {}
        for q in self.queries:
            if q.sql.strip().upper().startswith("SELECT"):
                # Normalize query to find patterns
                pattern = self._normalize_query(q.sql)
                query_patterns[pattern] = query_patterns.get(pattern, 0) + 1

        # If any pattern appears many times, likely N+1
        for pattern, count in query_patterns.items():
            if count >= threshold:
                return True

        return False

    def _normalize_query(self, sql: str) -> str:
        """Normalize a query to identify patterns."""
        import re
        # Remove parameter values
        normalized = re.sub(r"'[^']*'", "'?'", sql)
        normalized = re.sub(r"\b\d+\b", "?", normalized)
        # Remove extra whitespace
        normalized = " ".join(normalized.split())
        return normalized.upper()

    def get_slow_queries(self, threshold_ms: float = 100) -> List[QueryInfo]:
        """Get queries that took longer than the threshold."""
        return [q for q in self.queries if q.duration_ms > threshold_ms]

    def summary(self) -> str:
        """Generate a summary of query statistics."""
        lines = [
            f"Query Statistics:",
            f"  Total queries: {self.count}",
            f"  SELECT: {self.select_count}",
            f"  INSERT: {self.insert_count}",
            f"  UPDATE: {self.update_count}",
            f"  DELETE: {self.delete_count}",
            f"  Total query time: {self.total_duration_ms:.2f}ms",
            f"  Total elapsed: {self.elapsed_ms:.2f}ms",
        ]

        slow = self.get_slow_queries()
        if slow:
            lines.append(f"  Slow queries (>100ms): {len(slow)}")

        if self.has_n_plus_one():
            lines.append("  ⚠️  POTENTIAL N+1 QUERY DETECTED!")

        return "\n".join(lines)


class QueryCounter:
    """
    Context manager for counting and analyzing database queries.

    Usage:
        async with QueryCounter() as counter:
            await repository.list_all()

        print(f"Executed {counter.count} queries")
        assert not counter.stats.has_n_plus_one()
    """

    def __init__(self, log_queries: bool = False, engine=None):
        """
        Initialize query counter.

        Args:
            log_queries: Whether to log each query as it executes
            engine: SQLAlchemy engine to monitor (auto-detected if not provided)
        """
        self.log_queries = log_queries
        self.engine = engine
        self.stats = QueryStats()
        self._original_execute = None

    @property
    def count(self) -> int:
        """Shortcut to get query count."""
        return self.stats.count

    async def __aenter__(self):
        """Start counting queries (async context)."""
        self._setup_logging()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Stop counting and restore original behavior."""
        self.stats.end_time = time.time()
        self._teardown_logging()

        if self.log_queries:
            logger.info(self.stats.summary())

    def __enter__(self):
        """Start counting queries (sync context)."""
        self._setup_logging()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop counting and restore original behavior."""
        self.stats.end_time = time.time()
        self._teardown_logging()

        if self.log_queries:
            logger.info(self.stats.summary())

    def _setup_logging(self):
        """Set up SQLAlchemy event listeners for query logging."""
        try:
            from sqlalchemy import event
            from sqlalchemy.engine import Engine

            # Get engine if not provided
            if self.engine is None:
                try:
                    from database.async_engine import get_sync_engine
                    self.engine = get_sync_engine()
                except ImportError:
                    pass

            if self.engine:
                @event.listens_for(Engine, "before_cursor_execute")
                def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                    context._query_start_time = time.time()

                @event.listens_for(Engine, "after_cursor_execute")
                def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                    duration = (time.time() - context._query_start_time) * 1000

                    query_info = QueryInfo(
                        sql=statement,
                        parameters=parameters if isinstance(parameters, dict) else None,
                        duration_ms=duration,
                    )
                    self.stats.queries.append(query_info)

                    if self.log_queries:
                        logger.debug(f"Query: {query_info}")

                self._before_listener = before_cursor_execute
                self._after_listener = after_cursor_execute

        except ImportError:
            logger.warning("SQLAlchemy not available for query counting")

    def _teardown_logging(self):
        """Remove SQLAlchemy event listeners."""
        try:
            from sqlalchemy import event
            from sqlalchemy.engine import Engine

            if hasattr(self, '_before_listener'):
                event.remove(Engine, "before_cursor_execute", self._before_listener)
            if hasattr(self, '_after_listener'):
                event.remove(Engine, "after_cursor_execute", self._after_listener)
        except (ImportError, Exception):
            pass


def assert_query_count(max_queries: int, fail_on_n_plus_one: bool = True):
    """
    Decorator to assert maximum query count for a test function.

    Usage:
        @assert_query_count(max_queries=5)
        async def test_efficient_loading():
            await repository.list_with_eager_load()

    Args:
        max_queries: Maximum allowed queries
        fail_on_n_plus_one: Also fail if N+1 pattern detected
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            async with QueryCounter(log_queries=True) as counter:
                result = await func(*args, **kwargs)

            if counter.count > max_queries:
                raise AssertionError(
                    f"Query count {counter.count} exceeds maximum {max_queries}\n"
                    f"{counter.stats.summary()}"
                )

            if fail_on_n_plus_one and counter.stats.has_n_plus_one():
                raise AssertionError(
                    f"N+1 query pattern detected!\n"
                    f"{counter.stats.summary()}"
                )

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with QueryCounter(log_queries=True) as counter:
                result = func(*args, **kwargs)

            if counter.count > max_queries:
                raise AssertionError(
                    f"Query count {counter.count} exceeds maximum {max_queries}\n"
                    f"{counter.stats.summary()}"
                )

            if fail_on_n_plus_one and counter.stats.has_n_plus_one():
                raise AssertionError(
                    f"N+1 query pattern detected!\n"
                    f"{counter.stats.summary()}"
                )

            return result

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# =============================================================================
# EAGER LOADING HELPERS
# =============================================================================

def recommend_eager_loading(stats: QueryStats) -> List[str]:
    """
    Analyze query patterns and recommend eager loading strategies.

    Returns list of recommendations based on detected patterns.
    """
    recommendations = []

    if stats.has_n_plus_one():
        recommendations.append(
            "⚠️ N+1 pattern detected. Consider using:\n"
            "  - joinedload() for to-one relationships\n"
            "  - selectinload() for to-many relationships\n"
            "  - subqueryload() for complex queries"
        )

    # Check for repeated similar queries
    query_patterns = {}
    for q in stats.queries:
        pattern = stats._normalize_query(q.sql)
        if pattern not in query_patterns:
            query_patterns[pattern] = []
        query_patterns[pattern].append(q)

    for pattern, queries in query_patterns.items():
        if len(queries) > 5 and "SELECT" in pattern:
            # Try to identify the table
            import re
            table_match = re.search(r"FROM\s+(\w+)", pattern)
            table = table_match.group(1) if table_match else "related_table"

            recommendations.append(
                f"Pattern repeated {len(queries)} times on '{table}':\n"
                f"  Consider: query.options(selectinload(Model.{table}))"
            )

    return recommendations
