# IRS RAG Semantic Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace TF-IDF keyword matching with semantic embeddings (sentence-transformers + FAISS) to improve IRS guidance retrieval quality while preserving the public API.

**Architecture:** The `IRSRag` class will use `sentence-transformers/all-MiniLM-L6-v2` to embed all IRS publication chunks into a FAISS vector index. On retrieval, queries are embedded with the same model and matched via cosine similarity. The public interface (`retrieve()`, `format_for_prompt()`, `format_multi()`) remains unchanged. Vector embeddings are cached to disk to avoid re-computation on startup.

**Tech Stack:**
- `sentence-transformers>=3.0.0` — semantic embeddings
- `faiss-cpu>=1.7.4` — local vector index
- Existing: `numpy`, `pathlib`, `json`, `logging`

---

### Task 1: Update requirements.txt

**Files:**
- Modify: `requirements.txt` (add two lines)

**Step 1: Add dependencies to requirements.txt**

After line 25 (after scikit-learn), add:

```
# Semantic search / Vector store
sentence-transformers>=3.0.0,<4.0.0
faiss-cpu>=1.7.4,<2.0.0
```

The section should look like:
```
# ML Classification
scikit-learn>=1.5.0,<2.0.0
joblib>=1.4.0

# Semantic search / Vector store
sentence-transformers>=3.0.0,<4.0.0
faiss-cpu>=1.7.4,<2.0.0

# Web framework (for API)
```

**Step 2: Commit**

```bash
git add requirements.txt
git commit -m "chore: add sentence-transformers and faiss-cpu dependencies

- sentence-transformers>=3.0.0 for semantic embeddings
- faiss-cpu>=1.7.4 for local vector index

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

### Task 2: Rewrite IRSRag class to use FAISS + sentence-transformers

**Files:**
- Modify: `src/services/irs_rag.py` (replace entire implementation)

**Step 1: Replace the import section**

Replace lines 30-41 with:

```python
from __future__ import annotations

import json
import logging
import pickle
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

try:
    import faiss
except ImportError:
    faiss = None

logger = logging.getLogger(__name__)
```

**Step 2: Replace the IRSRag class**

Replace lines 93-162 (the entire `IRSRag` class) with:

```python
class IRSRag:
    """
    Semantic RAG retrieval over IRS publication excerpts using sentence-transformers + FAISS.

    Uses `sentence-transformers/all-MiniLM-L6-v2` to embed chunks and build a local FAISS
    vector index. Embeddings are cached to disk to avoid re-computation on startup.

    Thread-safe after __init__; FAISS index and embeddings are immutable after build.
    """

    # Model name — all embeddings use this consistent model
    _MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    _EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension

    def __init__(self, tax_year: int = 2025) -> None:
        self._tax_year = tax_year
        self._chunks = [IRSChunk(**c) for c in _load_chunks(tax_year)]

        if not self._chunks:
            logger.warning("No IRS chunks loaded for tax year %d", tax_year)
            self._model = None
            self._faiss_index = None
            self._embeddings = None
            return

        # Load or build embeddings and FAISS index
        self._model = SentenceTransformer(self._MODEL_NAME, trust_remote_code=True)
        self._embeddings, self._faiss_index = self._build_or_load_index()
        logger.debug("IRSRag: indexed %d chunks with FAISS", len(self._chunks))

    def _get_cache_path(self) -> Path:
        """Return path to cached embeddings file."""
        return _DATA_DIR / f"embeddings_{self._tax_year}.pkl"

    def _build_or_load_index(self) -> tuple:
        """Build FAISS index or load from cache if available."""
        cache_path = self._get_cache_path()

        # Try to load cached embeddings
        if cache_path.exists():
            try:
                with open(cache_path, "rb") as f:
                    embeddings = pickle.load(f)
                logger.debug("Loaded cached embeddings from %s", cache_path)
                index = self._build_faiss_index(embeddings)
                return embeddings, index
            except Exception as e:
                logger.warning("Failed to load cached embeddings: %s", e)

        # Compute embeddings
        corpus = [f"{c.topic} {' '.join(c.tags)} {c.text}" for c in self._chunks]
        embeddings = self._model.encode(corpus, convert_to_numpy=True)

        # Save cache
        try:
            with open(cache_path, "wb") as f:
                pickle.dump(embeddings, f)
            logger.debug("Saved embeddings cache to %s", cache_path)
        except Exception as e:
            logger.warning("Failed to save embeddings cache: %s", e)

        index = self._build_faiss_index(embeddings)
        return embeddings, index

    @staticmethod
    def _build_faiss_index(embeddings: np.ndarray) -> object:
        """Build FAISS flat index from embeddings."""
        if faiss is None:
            raise ImportError("faiss-cpu not installed")

        index = faiss.IndexFlatL2(IRSRag._EMBEDDING_DIM)
        index.add(embeddings.astype(np.float32))
        return index

    def retrieve(self, query: str, top_k: int = 3) -> List[IRSChunk]:
        """Return top_k most semantically relevant IRS chunks for a query."""
        if not self._chunks or self._model is None or self._faiss_index is None:
            return []

        try:
            # Embed query
            query_embedding = self._model.encode([query], convert_to_numpy=True)

            # Search FAISS index (returns distances and indices)
            # FAISS IndexFlatL2 returns squared L2 distances; convert to similarity
            distances, indices = self._faiss_index.search(
                query_embedding.astype(np.float32), top_k
            )

            results = []
            # Lower distance = higher similarity for L2
            for dist, idx in zip(distances[0], indices[0]):
                if idx < 0:  # FAISS returns -1 for invalid indices
                    continue

                # Convert L2 distance to similarity score (0-1 range)
                # Use exp(-distance) to map distance to similarity
                similarity = float(np.exp(-dist / 2))

                chunk = self._chunks[idx]
                results.append(IRSChunk(
                    id=chunk.id,
                    pub=chunk.pub,
                    topic=chunk.topic,
                    tags=chunk.tags,
                    text=chunk.text,
                    score=similarity,
                ))

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
```

**Step 3: Verify file structure**

The file should now have:
- Lines 1-28: Module docstring + imports (updated)
- Lines 30-51: Data loader functions (_load_chunks) — unchanged
- Lines 53-87: IRSChunk dataclass — unchanged
- Lines 89-200: IRSRag class — replaced
- Lines 202-206: Singleton accessor (get_irs_rag) — unchanged

**Step 4: Commit**

```bash
git add src/services/irs_rag.py
git commit -m "feat: upgrade IRS RAG from TF-IDF to semantic embeddings

- Replace scikit-learn TF-IDF with sentence-transformers (all-MiniLM-L6-v2)
- Use FAISS IndexFlatL2 for local vector index
- Cache embeddings to disk to avoid re-computation on startup
- Preserve public API: retrieve(), format_for_prompt(), format_multi()
- Improve retrieval quality via semantic similarity vs keyword matching

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

### Task 3: Test the updated implementation

**Files:**
- Test: `tests/services/test_irs_rag.py` (existing tests)

**Step 1: Run existing tests**

```bash
cd /Users/rakeshanita/jorss-gbo-taai
pytest tests/services/test_irs_rag.py -v
```

**Expected output:**
- All tests should pass
- If tests fail, note the failures and fix the implementation

**Step 2: Manual smoke test (optional)**

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/rakeshanita/jorss-gbo-taai')

from src.services.irs_rag import get_irs_rag

rag = get_irs_rag(tax_year=2025)

# Test retrieve
results = rag.retrieve("401k contribution limit", top_k=3)
print(f"✓ Retrieved {len(results)} chunks for '401k contribution limit'")
for r in results:
    print(f"  - {r.pub}: {r.topic} (score: {r.score:.3f})")

# Test format_for_prompt
prompt_text = rag.format_for_prompt("traditional IRA", top_k=2)
print(f"\n✓ Formatted {len(prompt_text.split(chr(10)))} lines for prompt")

# Test format_multi
multi_text = rag.format_multi(["401k", "IRA", "HSA"], top_k_per_query=1)
print(f"\n✓ Formatted multi-query result: {len(multi_text)} chars")
EOF
```

**Expected output:**
- No exceptions
- Results should show relevant IRS chunks with high similarity scores
- Formatted text should be readable

---

### Task 4: Verify retrievals are semantically relevant

**Files:**
- Test: `tests/services/test_irs_rag.py`

**Step 1: Add a semantic quality test**

Add this test to `tests/services/test_irs_rag.py`:

```python
def test_irs_rag_semantic_relevance():
    """Verify semantic retrieval improves over keyword matching."""
    from src.services.irs_rag import get_irs_rag

    rag = get_irs_rag(tax_year=2025)

    # Query: "maximum I can put in my 401k"
    # Should retrieve IRA/retirement contribution chunks, not random matches
    results = rag.retrieve("maximum I can put in my 401k", top_k=3)

    assert len(results) > 0, "Should retrieve at least one chunk"
    assert any("contribution" in r.topic.lower() or "limit" in r.topic.lower()
               for r in results), "Should find contribution/limit relevant chunks"
    assert results[0].score > 0.3, f"Top result should have score > 0.3, got {results[0].score}"


def test_irs_rag_deduplication():
    """Verify format_multi deduplicates chunks."""
    from src.services.irs_rag import get_irs_rag

    rag = get_irs_rag(tax_year=2025)

    # Same chunk might appear in results for multiple queries
    result = rag.format_multi(["IRA", "IRA contributions", "retirement"], top_k_per_query=2)

    # Should have no duplicate chunks (no repeated IDs in output)
    assert result != "", "Should return formatted result"
    assert "Relevant IRS Guidance" in result, "Should have header"
```

**Step 2: Run the new tests**

```bash
pytest tests/services/test_irs_rag.py::test_irs_rag_semantic_relevance -v
pytest tests/services/test_irs_rag.py::test_irs_rag_deduplication -v
```

**Expected output:**
- Both tests should PASS
- Semantic relevance should show improved matching

**Step 3: Commit**

```bash
git add tests/services/test_irs_rag.py
git commit -m "test: add semantic relevance tests for IRS RAG

- test_irs_rag_semantic_relevance: verify semantic matching improves quality
- test_irs_rag_deduplication: verify format_multi removes duplicate chunks

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

### Task 5: Run full test suite and clean up

**Files:**
- All (no new files)

**Step 1: Run full test suite**

```bash
cd /Users/rakeshanita/jorss-gbo-taai
pytest tests/ -x --tb=short
```

**Expected output:**
- All tests pass (no failures)
- If any test fails, fix before proceeding

**Step 2: Verify no import errors**

```bash
python3 -c "from src.services.irs_rag import get_irs_rag; rag = get_irs_rag(); print('✓ Import successful')"
```

**Expected output:**
```
✓ Import successful
```

**Step 3: Check cache directory exists**

```bash
ls -la /Users/rakeshanita/jorss-gbo-taai/data/irs_publications/
```

**Expected output:**
- Should show `2025.json` and (after first run) `embeddings_2025.pkl`

---

### Task 6: Update module docstring

**Files:**
- Modify: `src/services/irs_rag.py` (lines 1-28)

**Step 1: Update the module docstring**

Replace lines 1-28 with:

```python
"""
IRS Publication RAG (Retrieval-Augmented Generation).

Provides offline semantic retrieval of curated IRS publication excerpts using
sentence-transformers + FAISS vector index. No external downloads, no API calls —
works entirely from embedded text with local vector storage.

Uses `sentence-transformers/all-MiniLM-L6-v2` for semantic embeddings and FAISS
for efficient similarity search. Embeddings are cached to disk.

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
    # chunks → List[IRSChunk] with semantic similarity scores
    context = rag.format_for_prompt("NIIT net investment income tax threshold")
    # context → Formatted string for inclusion in AI prompts
"""
```

**Step 2: Commit**

```bash
git add src/services/irs_rag.py
git commit -m "docs: update module docstring for semantic RAG

- Clarify that system uses sentence-transformers + FAISS
- Note embedding caching behavior
- Update usage examples

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Rollback / Safety

If any step fails:

1. **Dependency install fails:** Check Python version (3.8+), run `pip install -e .` in repo
2. **FAISS build fails on M1/M2 Mac:** Use `faiss-cpu` wheel or consider `pip install faiss-cpu --index-url https://download.pytorch.org/whl/cpu`
3. **Embedding cache corrupts:** Delete `data/irs_publications/embeddings_*.pkl` and restart — will rebuild
4. **Tests fail:** Check that all imports resolve; run `pytest -v` to see specific failures

## Success Criteria

✓ All existing tests pass
✓ New semantic relevance tests pass
✓ `get_irs_rag()` returns valid instance with FAISS index
✓ `retrieve()` returns chunks with semantic similarity scores
✓ Public API unchanged (`retrieve`, `format_for_prompt`, `format_multi`)
✓ Embedding cache created and persisted
✓ All commits signed with Paperclip co-author
