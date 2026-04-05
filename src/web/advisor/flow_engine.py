"""Rule-based adaptive flow engine for the Intelligent Advisor.

Replaces the monolithic _get_dynamic_next_question() with a data-driven
question registry where each question declares its own eligibility rules
and relevance scoring.  The engine evaluates eligibility + scoring to
pick the single best next question for any given profile state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class FlowQuestion:
    """A single question in the adaptive flow."""

    id: str
    pool: str
    phase: int  # 1 = basics (must complete all before Phase 2), 2 = deep dive
    text: str
    actions: list[dict]
    eligibility: Callable[[dict], bool]  # profile → should this question appear?
    base_score: int  # 0-100 default relevance
    context_boost_keywords: list[str] = field(default_factory=list)
    context_boost_amount: int = 25
    sets_fields: list[str] = field(default_factory=list)
    skip_field: str = ""
    asked_field: str = ""
    follow_up_of: Optional[str] = None
    hint: str = ""  # One-line "why we're asking" shown below the question

    # ── eligibility check ──────────────────────────────────────────────

    def is_eligible(self, profile: dict) -> bool:
        """Return True if this question should be presented."""
        # Already asked?
        if self.asked_field and profile.get(self.asked_field):
            return False
        # Already skipped?
        if self.skip_field and profile.get(self.skip_field):
            return False
        # Already have ALL the data this question collects?
        if self.sets_fields and all(
            profile.get(f) is not None for f in self.sets_fields
        ):
            return False
        # Custom eligibility rule
        return self.eligibility(profile)

    # ── scoring ────────────────────────────────────────────────────────

    def score(self, profile: dict, context: str = "") -> int:
        """Calculate relevance score (higher = ask sooner)."""
        s = self.base_score
        if context and self.context_boost_keywords:
            for kw in self.context_boost_keywords:
                if kw in context:
                    s += self.context_boost_amount
                    break
        return s


# ═══════════════════════════════════════════════════════════════════════════
# Engine
# ═══════════════════════════════════════════════════════════════════════════

class FlowEngine:
    """Adaptive question engine — picks the best next question for a profile."""

    def __init__(self):
        try:
            from web.advisor.question_registry import ALL_QUESTIONS
        except ImportError:
            from src.web.advisor.question_registry import ALL_QUESTIONS
        self._questions: list[FlowQuestion] = ALL_QUESTIONS

    # ── public API ─────────────────────────────────────────────────────

    def get_next_question(
        self,
        profile: dict,
        conversation: Optional[list] = None,
    ) -> FlowQuestion | None:
        """Return the highest-priority eligible question, or None if done."""
        context = self._build_context(conversation)

        # Phase 1 must ALL complete before any Phase 2 question appears
        phase1_incomplete = any(
            q.phase == 1 and q.is_eligible(profile) for q in self._questions
        )

        best: tuple[int, str, FlowQuestion] | None = None
        for q in self._questions:
            if phase1_incomplete and q.phase != 1:
                continue
            if not q.is_eligible(profile):
                continue
            s = q.score(profile, context)
            candidate = (s, q.id, q)
            if best is None or (candidate[0] > best[0]) or (
                candidate[0] == best[0] and candidate[1] < best[1]
            ):
                best = candidate

        return best[2] if best else None

    def get_all_eligible(
        self,
        profile: dict,
        conversation: Optional[list] = None,
    ) -> list[FlowQuestion]:
        """Return all eligible questions sorted by score (for debugging)."""
        context = self._build_context(conversation)

        phase1_incomplete = any(
            q.phase == 1 and q.is_eligible(profile) for q in self._questions
        )

        eligible: list[tuple[int, str, FlowQuestion]] = []
        for q in self._questions:
            if phase1_incomplete and q.phase != 1:
                continue
            if q.is_eligible(profile):
                eligible.append((q.score(profile, context), q.id, q))

        eligible.sort(key=lambda x: (-x[0], x[1]))
        return [q for _, _, q in eligible]

    def count_remaining(self, profile: dict) -> int:
        """Count how many questions are still eligible."""
        return sum(1 for q in self._questions if q.is_eligible(profile))

    # ── internal ───────────────────────────────────────────────────────

    @staticmethod
    def _build_context(conversation: Optional[list]) -> str:
        if not conversation:
            return ""
        return " ".join(
            m.get("content", "")
            for m in conversation[-5:]
            if m.get("role") == "user"
        ).lower()
