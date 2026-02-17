"""Configurable weights and benchmarks for lead magnet Tax Health Score."""

from __future__ import annotations

import json
import os
from typing import Dict


DEFAULT_SCORE_WEIGHTS: Dict[str, float] = {
    "deduction_optimization": 0.28,
    "entity_structure": 0.17,
    "timing_strategy": 0.18,
    "compliance_risk": 0.17,
    "state_tax_efficiency": 0.10,
    "confidence": 0.10,
}

SCORE_BENCHMARKS: Dict[str, int] = {
    "average_taxpayer": 52,
    "cpa_optimized_target": 78,
}


def get_score_weights() -> Dict[str, float]:
    """
    Return normalized score weights.

    Optional env override:
      LEAD_MAGNET_SCORE_WEIGHTS='{"deduction_optimization":0.30,...}'
    """
    raw = os.environ.get("LEAD_MAGNET_SCORE_WEIGHTS", "").strip()
    weights = dict(DEFAULT_SCORE_WEIGHTS)

    if raw:
        try:
            candidate = json.loads(raw)
            if isinstance(candidate, dict):
                for key in weights:
                    value = candidate.get(key)
                    if isinstance(value, (int, float)) and value >= 0:
                        weights[key] = float(value)
        except Exception:
            # Keep defaults if override is invalid.
            pass

    total = sum(weights.values())
    if total <= 0:
        return dict(DEFAULT_SCORE_WEIGHTS)

    return {key: value / total for key, value in weights.items()}

