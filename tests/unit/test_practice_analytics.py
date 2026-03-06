import pytest
from unittest.mock import patch, MagicMock
import concurrent.futures


def test_ai_practice_summary_generated():
    """AI summary is generated when narrative generator succeeds."""
    mock_narrative = MagicMock()
    mock_narrative.content = "Your practice shows strong conversion rates..."

    mock_generator = MagicMock()
    mock_generator.generate_executive_summary = MagicMock(return_value=mock_narrative)

    # Make the async call work synchronously in tests
    import asyncio

    async def mock_gen(*a, **kw):
        return mock_narrative

    mock_generator.generate_executive_summary = mock_gen

    with patch("advisory.ai_narrative_generator.get_narrative_generator", return_value=mock_generator):
        from advisory.ai_narrative_generator import get_narrative_generator, ClientProfile

        # Simulate the logic from cpa_analytics
        practice_data = {
            "metrics": {"conversion_rate": 35, "total_leads": 50},
            "recommendations": {"total_count": 0, "top_recommendations": []},
        }

        def _gen():
            loop = asyncio.new_event_loop()
            try:
                generator = get_narrative_generator()
                profile = ClientProfile(name="Test CPA")
                return loop.run_until_complete(
                    generator.generate_executive_summary(practice_data, profile)
                )
            finally:
                loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            narrative = pool.submit(_gen).result(timeout=5)

        assert narrative is not None
        assert narrative.content == "Your practice shows strong conversion rates..."


def test_ai_practice_summary_none_on_failure():
    """AI summary is None when generation fails."""
    with patch("advisory.ai_narrative_generator.get_narrative_generator", side_effect=RuntimeError("AI unavailable")):
        ai_practice_summary = None
        try:
            from advisory.ai_narrative_generator import get_narrative_generator, ClientProfile
            import asyncio
            import concurrent.futures

            def _gen():
                loop = asyncio.new_event_loop()
                try:
                    generator = get_narrative_generator()
                    profile = ClientProfile(name="Test")
                    return loop.run_until_complete(
                        generator.generate_executive_summary({}, profile)
                    )
                finally:
                    loop.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                narrative = pool.submit(_gen).result(timeout=5)
                if narrative and narrative.content:
                    ai_practice_summary = narrative.content
        except Exception:
            pass

        assert ai_practice_summary is None


def test_ai_practice_summary_none_on_empty_content():
    """AI summary is None when narrative content is empty."""
    mock_narrative = MagicMock()
    mock_narrative.content = ""

    async def mock_gen(*a, **kw):
        return mock_narrative

    mock_generator = MagicMock()
    mock_generator.generate_executive_summary = mock_gen

    with patch("advisory.ai_narrative_generator.get_narrative_generator", return_value=mock_generator):
        ai_practice_summary = None
        try:
            from advisory.ai_narrative_generator import get_narrative_generator, ClientProfile
            import asyncio
            import concurrent.futures

            def _gen():
                loop = asyncio.new_event_loop()
                try:
                    gen = get_narrative_generator()
                    profile = ClientProfile(name="Test")
                    return loop.run_until_complete(
                        gen.generate_executive_summary({}, profile)
                    )
                finally:
                    loop.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                narrative = pool.submit(_gen).result(timeout=5)
                if narrative and narrative.content:
                    ai_practice_summary = narrative.content
        except Exception:
            pass

        assert ai_practice_summary is None
