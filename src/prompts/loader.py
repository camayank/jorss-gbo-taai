"""
Prompt Loader

Loads versioned system prompts from text files.
Allows prompt changes without code deployment.

Usage:
    from prompts.loader import load_prompt
    prompt = load_prompt("tax_agent", version="v1")
"""

import os
from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


@lru_cache(maxsize=32)
def load_prompt(name: str, version: str = "v1") -> str:
    """Load a prompt file by name and version.

    Looks for: src/prompts/{name}_{version}.txt
    Raises FileNotFoundError if not found.
    """
    filename = f"{name}_{version}.txt"
    filepath = _PROMPTS_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Prompt not found: {filepath}")
    return filepath.read_text().strip()
