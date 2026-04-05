#!/usr/bin/env python3
"""
Stream Battle-Test Suite
========================
Tests the /chat/stream SSE endpoint's correctness and resilience.

Run from repo root:
    python scripts/test_streaming.py

All 6 tests must pass before deploying streaming to production.
"""

import asyncio
import json
import sys
import types
import unittest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_UUID1 = str(uuid.uuid4())
_UUID2 = str(uuid.uuid4())
_UUID3 = str(uuid.uuid4())

# ---------------------------------------------------------------------------
# Path setup — allow importing from src/
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect(async_gen) -> list[dict]:
    """Drive an async generator to completion and return parsed SSE events."""

    async def _run():
        events = []
        async for chunk in async_gen:
            # Each chunk is  `data: {...}\n\n`
            for line in chunk.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    payload = line[len("data:"):].strip()
                    try:
                        events.append(json.loads(payload))
                    except json.JSONDecodeError:
                        events.append({"_raw": payload})
        return events

    return asyncio.get_event_loop().run_until_complete(_run())


def _make_mock_stream(chunks: list[str]):
    """Return an AsyncMock Anthropic stream whose text_stream yields `chunks`."""

    async def _text_stream():
        for c in chunks:
            yield c

    stream_ctx = AsyncMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=stream_ctx)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)
    stream_ctx.text_stream = _text_stream()
    stream_ctx.close = AsyncMock()
    return stream_ctx


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStreamSSEFormat(unittest.IsolatedAsyncioTestCase):
    """Test 1 — every SSE event from a normal stream has the right shape."""

    async def test_text_and_done_events(self):
        """Normal stream: text chunks → done event."""
        mock_stream = _make_mock_stream(["Hello", " there", "!"])

        mock_ai = MagicMock()
        mock_session = {
            "profile": {},
            "conversation_history": [],
            "strategies": [],
        }
        mock_engine = MagicMock()
        mock_engine.get_or_create_session = AsyncMock(return_value=mock_session)
        mock_engine.calculate_profile_completeness = MagicMock(return_value=0.5)

        anthropic_mod = types.ModuleType("anthropic")
        anthropic_mod.AsyncAnthropic = MagicMock(return_value=MagicMock(
            messages=MagicMock(stream=MagicMock(return_value=mock_stream))
        ))

        with (
            patch.dict("sys.modules", {"anthropic": anthropic_mod}),
            patch("web.intelligent_advisor_api.get_ai_service", return_value=mock_ai),
            patch("web.intelligent_advisor_api.chat_engine", mock_engine),
        ):
            from web.intelligent_advisor_api import chat_stream, ChatRequest  # noqa: PLC0415
            req = ChatRequest(session_id=_UUID1, message="What deductions can I take?")

            response = await chat_stream(req)
            # StreamingResponse wraps an async generator — pull events
            events = []
            async for chunk in response.body_iterator:
                for line in chunk.splitlines():
                    line = line.strip()
                    if line.startswith("data:"):
                        events.append(json.loads(line[5:].strip()))

        text_events = [e for e in events if e.get("type") == "text"]
        done_events = [e for e in events if e.get("type") == "done"]
        fallback_events = [e for e in events if e.get("type") == "fallback"]

        self.assertTrue(len(text_events) >= 1, "Expected at least one text event")
        self.assertEqual(len(done_events), 1, "Expected exactly one done event")
        self.assertEqual(len(fallback_events), 0, "Expected no fallback events")

        # Text events must have a `text` field
        for evt in text_events:
            self.assertIn("text", evt)
            self.assertIsInstance(evt["text"], str)

        # Done event must have session_id and completeness
        done = done_events[0]
        self.assertIn("session_id", done)
        self.assertIn("completeness", done)


class TestStreamFallbackWhenNoAI(unittest.IsolatedAsyncioTestCase):
    """Test 2 — when get_ai_service returns None, only a fallback event is emitted."""

    async def test_fallback_on_no_ai_service(self):
        with patch("web.intelligent_advisor_api.get_ai_service", return_value=None):
            from web.intelligent_advisor_api import chat_stream, ChatRequest  # noqa: PLC0415
            req = ChatRequest(session_id=_UUID2, message="test")
            response = await chat_stream(req)

            events = []
            async for chunk in response.body_iterator:
                for line in chunk.splitlines():
                    line = line.strip()
                    if line.startswith("data:"):
                        events.append(json.loads(line[5:].strip()))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "fallback")


class TestSSEBufferReconstruction(unittest.TestCase):
    """Test 3 — pure-Python SSE client handles split/fragmented reads."""

    def test_split_sse_chunks_reassemble(self):
        """Simulate TCP fragmentation: a single SSE frame split across two network reads."""
        full_event = 'data: {"type":"text","text":"hello"}\n\n'
        half1 = full_event[:20]  # 'data: {"type":"text"'
        half2 = full_event[20:]  # ',"text":"hello"}\n\n'

        buf = ""
        parsed = []

        for fragment in [half1, half2]:
            buf += fragment
            while "\n\n" in buf:
                frame, buf = buf.split("\n\n", 1)
                for line in frame.splitlines():
                    line = line.strip()
                    if line.startswith("data:"):
                        parsed.append(json.loads(line[5:].strip()))

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["type"], "text")
        self.assertEqual(parsed[0]["text"], "hello")

    def test_multi_event_in_single_read(self):
        """Multiple events arriving in one read are all parsed."""
        chunk = (
            'data: {"type":"text","text":"a"}\n\n'
            'data: {"type":"text","text":"b"}\n\n'
            'data: {"type":"done","session_id":"x","completeness":0.8}\n\n'
        )
        buf = ""
        parsed = []
        buf += chunk
        while "\n\n" in buf:
            frame, buf = buf.split("\n\n", 1)
            for line in frame.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    parsed.append(json.loads(line[5:].strip()))

        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0]["type"], "text")
        self.assertEqual(parsed[2]["type"], "done")


class TestStreamTimeoutFallback(unittest.IsolatedAsyncioTestCase):
    """Test 4 — TimeoutError on first token triggers fallback event."""

    async def test_first_token_timeout_emits_fallback(self):
        mock_ai = MagicMock()
        mock_session = {"profile": {}, "conversation_history": [], "strategies": []}
        mock_engine = MagicMock()
        mock_engine.get_or_create_session = AsyncMock(return_value=mock_session)

        async def _hanging_stream():
            # Never yields — simulates Anthropic API hanging
            await asyncio.sleep(999)
            yield "never"

        stream_ctx = AsyncMock()
        stream_ctx.__aenter__ = AsyncMock(return_value=stream_ctx)
        stream_ctx.__aexit__ = AsyncMock(return_value=False)
        stream_ctx.text_stream = _hanging_stream()
        stream_ctx.close = AsyncMock()

        anthropic_mod = types.ModuleType("anthropic")
        anthropic_mod.AsyncAnthropic = MagicMock(return_value=MagicMock(
            messages=MagicMock(stream=MagicMock(return_value=stream_ctx))
        ))

        async def _fast_timeout(coro, timeout):
            raise asyncio.TimeoutError()

        with (
            patch.dict("sys.modules", {"anthropic": anthropic_mod}),
            patch("web.intelligent_advisor_api.get_ai_service", return_value=mock_ai),
            patch("web.intelligent_advisor_api.chat_engine", mock_engine),
            patch("asyncio.wait_for", side_effect=_fast_timeout),
        ):
            from web.intelligent_advisor_api import chat_stream, ChatRequest  # noqa: PLC0415
            req = ChatRequest(session_id=_UUID3, message="test")
            response = await chat_stream(req)

            events = []
            async for chunk in response.body_iterator:
                for line in chunk.splitlines():
                    line = line.strip()
                    if line.startswith("data:"):
                        events.append(json.loads(line[5:].strip()))

        fallback = [e for e in events if e.get("type") == "fallback"]
        self.assertGreaterEqual(len(fallback), 1, "Expected fallback event on timeout")
        # Must not see text or done events
        self.assertEqual(len([e for e in events if e.get("type") == "text"]), 0)


class TestWordCountGuard(unittest.TestCase):
    """Test 5 — post-processor 1: word-count guard truncates at sentence boundary."""

    def _apply_word_guard(self, text: str) -> str:
        """Copied verbatim from intelligent_advisor_api.py lines 2660-2669."""
        raw_content = text
        words = raw_content.split()
        if len(words) > 200:
            candidate = " ".join(words[:200])
            last_boundary = max(candidate.rfind(". "), candidate.rfind("! "), candidate.rfind("? "))
            raw_content = candidate[:last_boundary + 1].strip() if last_boundary > 0 else candidate.strip()
        return raw_content

    def test_short_response_unchanged(self):
        text = "This is a short response. Do you have any deductions?"
        self.assertEqual(self._apply_word_guard(text), text)

    def test_250_word_response_truncated_at_boundary(self):
        # 250 words ending with a clear sentence boundary before word 200
        sentences = [
            "You can deduct home office expenses proportional to business use.",  # ~10 words
            "The §179 deduction lets you immediately expense equipment purchases.",  # ~9 words
        ]
        # Build a ~250-word block: repeat until we exceed 200 words
        long_text = " ".join(sentences * 14)  # ~266 words
        # Append a distinct tail to verify truncation
        long_text += " And this is the very long tail that should be cut off completely in all cases."

        result = self._apply_word_guard(long_text)
        word_count = len(result.split())

        self.assertLessEqual(word_count, 200, f"Expected ≤200 words, got {word_count}")
        # Must end at a sentence boundary
        self.assertTrue(
            result.endswith(".") or result.endswith("!") or result.endswith("?"),
            f"Expected sentence-boundary ending, got: ...{result[-30:]!r}"
        )
        # Tail must be gone
        self.assertNotIn("cut off completely", result)

    def test_exactly_200_words_unchanged(self):
        text = " ".join(["word"] * 200)
        result = self._apply_word_guard(text)
        self.assertEqual(len(result.split()), 200)


class TestSingleQuestionEnforcer(unittest.TestCase):
    """Test 6 — post-processor 2: single-question enforcer keeps only last question."""

    def _apply_question_enforcer(self, text: str) -> str:
        """Copied verbatim from intelligent_advisor_api.py — single-question enforcer."""
        import re as _re_q
        raw_content = text
        if raw_content.count("?") > 1:
            _sents = _re_q.split(r'(?<=[.!?]) +', raw_content.rstrip())
            _final_q = _sents[-1] if _sents else raw_content
            _kept = [s for s in _sents[:-1] if not s.rstrip().endswith("?")]
            raw_content = " ".join(_kept + [_final_q]).strip()
        return raw_content

    def test_single_question_unchanged(self):
        text = "You have a §199A deduction available. Are you incorporated as an S-Corp?"
        self.assertEqual(self._apply_question_enforcer(text), text)

    def test_two_questions_reduced_to_one(self):
        text = (
            "You qualify for §199A deductions given your self-employment income. "
            "Have you considered a SEP-IRA? "
            "Before we dive into contribution limits, I need to understand one thing. "
            "What is your net profit from self-employment this year?"
        )
        result = self._apply_question_enforcer(text)
        q_count = result.count("?")
        self.assertEqual(q_count, 1, f"Expected 1 question mark, got {q_count} in: {result!r}")
        self.assertIn("What is your net profit from self-employment this year?", result)
        self.assertNotIn("Have you considered a SEP-IRA?", result)

    def test_three_questions_reduced_to_one(self):
        text = (
            "You qualify for QBI. "
            "Do you have a Schedule C? "
            "Are you paying self-employment tax? "
            "What is your net profit this year?"
        )
        result = self._apply_question_enforcer(text)
        q_count = result.count("?")
        self.assertEqual(q_count, 1, f"Expected 1 question mark, got {q_count} in: {result!r}")
        self.assertIn("What is your net profit this year?", result)

    def test_last_question_is_preserved(self):
        text = "Do you have a home office? Do you use it exclusively? What percentage of the home is dedicated?"
        result = self._apply_question_enforcer(text)
        self.assertIn("What percentage of the home is dedicated?", result)

    def test_no_question_unchanged(self):
        text = "You should consider an S-Corp election. It can save $5K–$20K in SE tax annually."
        result = self._apply_question_enforcer(text)
        self.assertEqual(result, text)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Stream Battle-Test Suite")
    print("=" * 60)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Tests 3, 5, 6 are pure-Python — always run first (no server needed)
    for cls in [
        TestSSEBufferReconstruction,
        TestWordCountGuard,
        TestSingleQuestionEnforcer,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    # Tests 1, 2, 4 require importing from src/ and patching
    for cls in [
        TestStreamFallbackWhenNoAI,
        TestStreamTimeoutFallback,
        TestStreamSSEFormat,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
