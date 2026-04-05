"""
opportunity_detector — split modules for TaxOpportunityDetector.

Each submodule handles one concern:
  context.py    — DetectionContext (per-call engine results, replaces global caches)
  engine.py     — EngineDetector  (_detect_engine_insights, _detect_multiyear_planning)
  ai_detector.py — AIDetector      (_ai_detect_opportunities, 7 specialist passes)

The main TaxOpportunityDetector in services/tax_opportunity_detector.py
imports from here so callers see no change.
"""

from .context import DetectionContext  # noqa: F401
