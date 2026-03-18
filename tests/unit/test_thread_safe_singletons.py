"""Tests for thread-safe singleton accessors in the advisory package.

Covers:
- get_narrative_generator()  (ai_narrative_generator module)
- get_report_summarizer()    (report_summarizer module)

Each function uses a double-checked locking pattern with a threading.Lock
to guarantee that exactly one instance is created, even under concurrent
access from multiple threads.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock

import pytest

from advisory.ai_narrative_generator import get_narrative_generator
import advisory.ai_narrative_generator as narrative_mod

from advisory.report_summarizer import get_report_summarizer
import advisory.report_summarizer as summarizer_mod


# ---------------------------------------------------------------------------
# Fixtures — reset module-level singletons between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singletons():
    """Ensure each test starts with a clean singleton state."""
    narrative_mod._narrative_generator = None
    summarizer_mod._report_summarizer = None
    yield
    narrative_mod._narrative_generator = None
    summarizer_mod._report_summarizer = None


# ---------------------------------------------------------------------------
# Narrative generator singleton tests
# ---------------------------------------------------------------------------

@patch("advisory.ai_narrative_generator.AINarrativeGenerator", autospec=True)
def test_get_narrative_generator_returns_same_instance(mock_cls):
    """Repeated calls must return the exact same object."""
    instance = MagicMock()
    mock_cls.return_value = instance

    first = get_narrative_generator()
    second = get_narrative_generator()

    assert first is second
    mock_cls.assert_called_once()


# ---------------------------------------------------------------------------
# Report summarizer singleton tests
# ---------------------------------------------------------------------------

@patch("advisory.report_summarizer.AIReportSummarizer", autospec=True)
def test_get_report_summarizer_returns_same_instance(mock_cls):
    """Repeated calls must return the exact same object."""
    instance = MagicMock()
    mock_cls.return_value = instance

    first = get_report_summarizer()
    second = get_report_summarizer()

    assert first is second
    mock_cls.assert_called_once()


# ---------------------------------------------------------------------------
# Concurrent access tests
# ---------------------------------------------------------------------------

@patch("advisory.ai_narrative_generator.AINarrativeGenerator", autospec=True)
def test_concurrent_access_returns_same_narrative_generator(mock_cls):
    """Multiple threads calling get_narrative_generator() concurrently
    must all receive the same instance."""
    instance = MagicMock()
    mock_cls.return_value = instance

    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(get_narrative_generator) for _ in range(20)]
        for f in as_completed(futures):
            results.append(f.result())

    assert all(r is results[0] for r in results)
    mock_cls.assert_called_once()


@patch("advisory.report_summarizer.AIReportSummarizer", autospec=True)
def test_concurrent_access_returns_same_report_summarizer(mock_cls):
    """Multiple threads calling get_report_summarizer() concurrently
    must all receive the same instance."""
    instance = MagicMock()
    mock_cls.return_value = instance

    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(get_report_summarizer) for _ in range(20)]
        for f in as_completed(futures):
            results.append(f.result())

    assert all(r is results[0] for r in results)
    mock_cls.assert_called_once()


# ---------------------------------------------------------------------------
# Race-condition safety — constructor called exactly once
# ---------------------------------------------------------------------------

@patch("advisory.ai_narrative_generator.AINarrativeGenerator", autospec=True)
def test_singleton_created_only_once_under_race_conditions(mock_cls):
    """Even when many threads race to be first, the constructor must be
    invoked exactly once (double-checked locking guarantee)."""
    instance = MagicMock()
    mock_cls.return_value = instance

    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(get_narrative_generator) for _ in range(50)]
        for f in as_completed(futures):
            f.result()  # propagate exceptions

    mock_cls.assert_called_once()
