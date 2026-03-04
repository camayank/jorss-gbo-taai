"""Tests for versioned prompt loading."""

import pytest
from prompts.loader import load_prompt


class TestPromptLoader:

    def test_loads_existing_prompt(self):
        prompt = load_prompt("tax_agent", version="v1")
        assert "expert tax preparation" in prompt.lower() or "tax" in prompt.lower()
        assert len(prompt) > 100

    def test_raises_on_missing_prompt(self):
        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent", version="v1")

    def test_loads_reasoning_prompt(self):
        prompt = load_prompt("reasoning", version="v1")
        assert "IRC" in prompt

    def test_loads_research_prompt(self):
        prompt = load_prompt("research", version="v1")
        assert "sources" in prompt.lower()

    def test_loads_extraction_prompt(self):
        prompt = load_prompt("extraction", version="v1")
        assert "JSON" in prompt
