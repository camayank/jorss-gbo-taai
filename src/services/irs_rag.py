"""
IRS Publication RAG (Retrieval-Augmented Generation).

Provides offline retrieval of curated IRS publication excerpts using TF-IDF.
No external downloads, no API calls — works entirely from embedded text.

Covers key publications:
  Pub 17  — Your Federal Income Tax (general)
  Pub 590-A/B — IRA contributions & distributions
  Pub 969  — HSA / FSA / HRA
  Pub 946  — Depreciation (Section 179 / bonus)
  Pub 527  — Residential Rental Property
  Pub 936  — Home Mortgage Interest
  Pub 587  — Business Use of Home (home office)
  Pub 463  — Travel, Gift, Car Expenses
  Pub 525  — Taxable and Nontaxable Income
  Pub 550  — Investment Income and Expenses
  Pub 596  — Earned Income Credit
  Pub 972  — Child Tax Credit
  Pub 4681 — Cancelled Debts
  Pub 15-T — Federal Income Tax Withholding Methods

Usage:
    rag = get_irs_rag()
    chunks = rag.retrieve("401k contribution limit 2025", top_k=3)
    # chunks → List[IRSChunk]
    context = rag.format_for_prompt("NIIT net investment income tax threshold")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON data loader — replaces hardcoded _IRS_CHUNKS list
# ---------------------------------------------------------------------------

# Locate the data directory relative to this file:
#   src/services/irs_rag.py  →  ../../data/irs_publications/
_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "irs_publications"


def _load_chunks(tax_year: int = 2025) -> List[dict]:
    """Load IRS publication chunks from JSON data file for the given tax year."""
    path = _DATA_DIR / f"{tax_year}.json"
    if not path.exists():
        logger.warning(
            "IRS publications JSON not found at %s — using empty knowledge base", path
        )
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    chunks = data.get("chunks", [])
    logger.debug("Loaded %d IRS publication chunks for tax year %d", len(chunks), tax_year)
    return chunks


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# IRSChunk dataclass
# ---------------------------------------------------------------------------

@dataclass
class IRSChunk:
    id: str
    pub: str
    topic: str
    tags: List[str]
    text: str
    score: float = 0.0

    def to_prompt_string(self) -> str:
        return f"[{self.pub} — {self.topic}]\n{self.text}"


# ---------------------------------------------------------------------------
# IRS RAG engine
# ---------------------------------------------------------------------------

class IRSRag:
    """
    TF-IDF retrieval over curated IRS publication excerpts.

    Thread-safe after __init__; vectorizer is fit once.
    Data is loaded from data/irs_publications/{tax_year}.json — no code
    changes needed when tax year thresholds are updated annually.
    """

    def __init__(self, tax_year: int = 2025) -> None:
        self._tax_year = tax_year
        self._chunks = [IRSChunk(**c) for c in _load_chunks(tax_year)]
        self._corpus = [f"{c.topic} {' '.join(c.tags)} {c.text}" for c in self._chunks]

        self._vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            stop_words="english",
            sublinear_tf=True,
        )
        self._tfidf_matrix = self._vectorizer.fit_transform(self._corpus)
        logger.debug("IRSRag: indexed %d chunks", len(self._chunks))

    def retrieve(self, query: str, top_k: int = 3) -> List[IRSChunk]:
        """Return top_k most relevant IRS chunks for a query."""
        try:
            q_vec = self._vectorizer.transform([query])
            scores = cosine_similarity(q_vec, self._tfidf_matrix).flatten()
            top_idx = np.argsort(scores)[::-1][:top_k]
            results = []
            for i in top_idx:
                if scores[i] > 0.01:
                    chunk = self._chunks[i]
                    chunk = IRSChunk(
                        id=chunk.id, pub=chunk.pub, topic=chunk.topic,
                        tags=chunk.tags, text=chunk.text, score=float(scores[i]),
                    )
                    results.append(chunk)
            return results
        except Exception as e:
            logger.warning("IRSRag.retrieve failed: %s", e)
            return []

    def format_for_prompt(self, query: str, top_k: int = 3) -> str:
        """Return a formatted string block for inclusion in AI prompts."""
        chunks = self.retrieve(query, top_k=top_k)
        if not chunks:
            return ""
        lines = ["=== Relevant IRS Guidance ==="]
        for c in chunks:
            lines.append(c.to_prompt_string())
            lines.append("")
        return "\n".join(lines)

    def format_multi(self, queries: List[str], top_k_per_query: int = 2) -> str:
        """Retrieve and deduplicate chunks for multiple queries."""
        seen: set = set()
        chunks: List[IRSChunk] = []
        for q in queries:
            for c in self.retrieve(q, top_k=top_k_per_query):
                if c.id not in seen:
                    seen.add(c.id)
                    chunks.append(c)
        if not chunks:
            return ""
        lines = ["=== Relevant IRS Guidance ==="]
        for c in chunks:
            lines.append(c.to_prompt_string())
            lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

@lru_cache(maxsize=4)
def get_irs_rag(tax_year: int = 2025) -> IRSRag:
    """Return a cached IRSRag instance for the given tax year."""
    return IRSRag(tax_year=tax_year)
