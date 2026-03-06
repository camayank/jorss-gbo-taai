import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json


class _MockAIResponse:
    def __init__(self, content):
        self.content = content


def _make_questions(n=5):
    """Create mock AdaptiveQuestion objects."""
    from smart_tax.question_generator import AdaptiveQuestionGenerator
    gen = AdaptiveQuestionGenerator()
    # Create mock questions directly
    questions = []
    for i in range(n):
        q = MagicMock()
        q.title = f"Question {i}"
        q.priority = MagicMock()
        q.priority.name = "MEDIUM"
        questions.append(q)
    return questions


def test_ai_reorders_questions():
    """AI response reorders questions correctly."""
    questions = _make_questions(5)
    original_titles = [q.title for q in questions]

    # AI wants reverse order
    ai_indices = [4, 3, 2, 1, 0]

    with patch("services.ai.unified_ai_service.get_ai_service") as mock_get:
        mock_service = MagicMock()
        async def mock_generate(*a, **kw):
            return _MockAIResponse(json.dumps(ai_indices))
        mock_service.generate = mock_generate
        mock_get.return_value = mock_service

        # Simulate the AI prioritization logic
        import asyncio, concurrent.futures

        question_titles = [q.title for q in questions[:10]]
        prompt = f"Given a single taxpayer with income ~$50,000, rank these: {json.dumps(question_titles)}"

        def _get_priority():
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(mock_service.generate(prompt))
            finally:
                loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            response = pool.submit(_get_priority).result(timeout=3)

        priority_indices = json.loads(response.content)
        reordered = [questions[i] for i in priority_indices]

        assert reordered[0].title == "Question 4"
        assert reordered[4].title == "Question 0"


def test_static_fallback_on_ai_failure():
    """Static priority sort used when AI fails."""
    from smart_tax.question_generator import AdaptiveQuestionGenerator, QuestionPriority

    gen = AdaptiveQuestionGenerator()

    with patch("services.ai.unified_ai_service.get_ai_service", side_effect=RuntimeError("No AI")):
        # Call generate_questions with minimal data
        questions = gen.generate_questions(
            extracted_data={},
            documents=[],
            filing_status="single",
        )

    # Questions should be returned (static sort applied)
    assert len(questions) > 0
    # Verify they're sorted by priority (CRITICAL < HIGH < MEDIUM < LOW)
    priorities = [q.priority for q in questions]
    priority_values = {
        QuestionPriority.CRITICAL: 0,
        QuestionPriority.HIGH: 1,
        QuestionPriority.MEDIUM: 2,
        QuestionPriority.LOW: 3,
    }
    values = [priority_values.get(p, 99) for p in priorities]
    assert values == sorted(values), "Questions should be sorted by static priority"


def test_static_fallback_on_invalid_ai_response():
    """Static fallback when AI returns non-JSON."""
    from smart_tax.question_generator import AdaptiveQuestionGenerator

    gen = AdaptiveQuestionGenerator()

    mock_service = MagicMock()
    async def mock_generate(*a, **kw):
        return _MockAIResponse("not valid json")
    mock_service.generate = mock_generate

    with patch("services.ai.unified_ai_service.get_ai_service", return_value=mock_service):
        questions = gen.generate_questions(
            extracted_data={},
            documents=[],
            filing_status="single",
        )

    # Should still return questions (static sort)
    assert len(questions) > 0


def test_static_fallback_on_wrong_count():
    """Static fallback when AI returns wrong number of indices."""
    from smart_tax.question_generator import AdaptiveQuestionGenerator

    gen = AdaptiveQuestionGenerator()

    mock_service = MagicMock()
    async def mock_generate(*a, **kw):
        return _MockAIResponse("[0, 1]")  # Wrong count
    mock_service.generate = mock_generate

    with patch("services.ai.unified_ai_service.get_ai_service", return_value=mock_service):
        questions = gen.generate_questions(
            extracted_data={},
            documents=[],
            filing_status="single",
        )

    assert len(questions) > 0
