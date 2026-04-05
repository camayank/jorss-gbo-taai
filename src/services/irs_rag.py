"""
IRS Publication RAG (Retrieval-Augmented Generation).

Provides offline retrieval of curated IRS publication excerpts using semantic embeddings.
Uses sentence-transformers (all-MiniLM-L6-v2) + FAISS for efficient vector similarity search.
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
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

logger = logging.getLogger(__name__)

# Locate the data directory relative to this file:
#   src/services/irs_rag.py  →  ../../data/irs_publications/
_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "irs_publications"

# Locate the embeddings cache directory for FAISS indices
_EMBEDDINGS_CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "irs_embeddings"


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


@dataclass
class IRSChunk:
    """Represents a single IRS publication excerpt."""

    id: str
    pub: str
    topic: str
    tags: List[str]
    text: str
    score: float = 0.0

    def to_prompt_string(self) -> str:
        return f"[{self.pub} — {self.topic}]\n{self.text}"


class SemanticIRSRag:
    """
    Semantic retrieval over curated IRS publication excerpts using sentence-transformers + FAISS.

    Uses all-MiniLM-L6-v2 for semantic embeddings and FAISS for efficient similarity search.
    Indexes are cached locally for fast startup. Thread-safe after __init__.
    """

    # Model to use for semantic embeddings
    _MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, tax_year: int = 2025) -> None:
        self._tax_year = tax_year
        self._chunks = [IRSChunk(**c) for c in _load_chunks(tax_year)]

        if not self._chunks:
            logger.warning("No IRS chunks loaded — RAG will return empty results")
            self._model = None
            self._faiss_index = None
            return

        # Create embeddings cache directory
        _EMBEDDINGS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Load model
        logger.debug(f"Loading embedding model: {self._MODEL_NAME}")
        self._model = SentenceTransformer(self._MODEL_NAME)

        # Try to load cached embeddings, otherwise compute
        cache_path = _EMBEDDINGS_CACHE_DIR / f"{tax_year}.faiss"
        if cache_path.exists():
            logger.debug(f"Loading cached FAISS index from {cache_path}")
            self._faiss_index = faiss.read_index(str(cache_path))
        else:
            # Compute embeddings for all chunks
            logger.debug(f"Computing embeddings for {len(self._chunks)} chunks")
            corpus_texts = [
                f"{c['topic']} {' '.join(c['tags'])} {c['text']}"
                for c in _load_chunks(tax_year)
            ]
            embeddings = self._model.encode(corpus_texts, convert_to_numpy=True)

            # Create and populate FAISS index
            dimension = embeddings.shape[1]
            self._faiss_index = faiss.IndexFlatL2(dimension)
            self._faiss_index.add(embeddings.astype(np.float32))

            # Cache the index
            faiss.write_index(self._faiss_index, str(cache_path))
            logger.debug(f"Cached FAISS index to {cache_path}")

        logger.debug(
            "SemanticIRSRag: indexed %d chunks with semantic embeddings",
            len(self._chunks),
        )

    def retrieve(self, query: str, top_k: int = 3) -> List[IRSChunk]:
        """Return top_k most relevant IRS chunks using semantic similarity."""
        if not self._chunks or self._model is None or self._faiss_index is None:
            return []

        try:
            # Embed the query
            query_embedding = self._model.encode([query], convert_to_numpy=True)

            # Search in FAISS index
            # FAISS uses L2 distance, so smaller distances = more similar
            distances, indices = self._faiss_index.search(
                query_embedding.astype(np.float32), top_k
            )

            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx < len(self._chunks):
                    chunk_data = self._chunks[idx]
                    # Convert L2 distance to a similarity-like score (0-1 range)
                    # Smaller distances = higher similarity
                    similarity_score = 1.0 / (1.0 + float(dist))
                    results.append(
                        IRSChunk(
                            id=chunk_data.id,
                            pub=chunk_data.pub,
                            topic=chunk_data.topic,
                            tags=chunk_data.tags,
                            text=chunk_data.text,
                            score=similarity_score,
                        )
                    )
            return results
        except Exception as e:
            logger.warning("SemanticIRSRag.retrieve failed: %s", e)
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


# Alias for backward compatibility
IRSRag = SemanticIRSRag


@lru_cache(maxsize=4)
def get_irs_rag(tax_year: int = 2025) -> SemanticIRSRag:
    """Return a cached SemanticIRSRag instance for the given tax year."""
    return SemanticIRSRag(tax_year=tax_year)
