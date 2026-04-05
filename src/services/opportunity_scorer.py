"""
OpportunityScorer: Ranks and filters TaxOpportunity objects by composite score.

Scoring weights:
  40% estimated_savings (log-normalized so $100K doesn't dominate $5K)
  30% profile_relevance (does this profile actually trigger this rule?)
  20% confidence (AI-assigned or 0.85 default for rule-based)
  10% actionability (has concrete action + deadline?)
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from typing import List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Import types (lazy to avoid circular import)
# ---------------------------------------------------------------------------

def _imports():
    from services.tax_opportunity_detector import (
        TaxOpportunity, TaxpayerProfile, OpportunityCategory, OpportunityPriority
    )
    return TaxOpportunity, TaxpayerProfile, OpportunityCategory, OpportunityPriority


# ---------------------------------------------------------------------------
# ScoredOpportunity
# ---------------------------------------------------------------------------

@dataclass
class ScoredOpportunity:
    opportunity: object          # TaxOpportunity
    composite_score: float       # 0–100
    savings_score: float
    relevance_score: float
    confidence_score: float
    actionability_score: float


# ---------------------------------------------------------------------------
# OpportunityScorer
# ---------------------------------------------------------------------------

class OpportunityScorer:
    """
    Scores and ranks TaxOpportunity objects against a TaxpayerProfile.

    Call score_and_rank() to get the top-k most actionable opportunities.
    Deduplicates by id before scoring.
    """

    def score_and_rank(
        self,
        opportunities: list,
        profile: object,
        top_k: Optional[int] = 25,
    ) -> list:
        """
        Return top_k opportunities sorted by composite score (highest first).

        top_k=None returns all opportunities (sorted but not truncated).
        Used by tests and bulk export scenarios.
        """
        # Deduplicate by id (keep first occurrence)
        seen: set = set()
        unique = []
        for o in opportunities:
            if o.id not in seen:
                seen.add(o.id)
                unique.append(o)

        scored = self.score_all(unique, profile)
        result = [s.opportunity for s in scored]
        return result if top_k is None else result[:top_k]

    def score_all(self, opportunities: list, profile: object) -> List[ScoredOpportunity]:
        """Score all opportunities and return sorted list (highest score first)."""
        scored = [self._score(o, profile) for o in opportunities]
        scored.sort(key=lambda s: s.composite_score, reverse=True)
        return scored

    def _score(self, o: object, profile: object) -> ScoredOpportunity:
        savings_s = self._savings_score(o)
        confidence_s = self._confidence_score(o)
        actionability_s = self._actionability_score(o)
        relevance_s = self._relevance_score(o, profile)

        composite = (
            savings_s       * 0.40 +
            relevance_s     * 0.30 +
            confidence_s    * 0.20 +
            actionability_s * 0.10
        )

        return ScoredOpportunity(
            opportunity=o,
            composite_score=round(composite, 2),
            savings_score=round(savings_s, 2),
            relevance_score=round(relevance_s, 2),
            confidence_score=round(confidence_s, 2),
            actionability_score=round(actionability_s, 2),
        )

    def _savings_score(self, o: object) -> float:
        """Log-normalized savings score 0–100.

        When estimated_savings is absent, falls back to priority as a proxy
        rather than returning a flat 50 for every unknown opportunity.
          HIGH   → 65  (strong signal even without a dollar figure)
          MEDIUM → 55
          LOW    → 45
          unknown → 50
        """
        savings = float(getattr(o, "estimated_savings", None) or 0)
        if savings > 0:
            return min(100.0, math.log1p(savings) / math.log1p(100_000) * 100)
        priority = getattr(o, "priority", None)
        p_val = (priority.value if priority and hasattr(priority, "value") else "").lower()
        return {"high": 65.0, "medium": 55.0, "low": 45.0}.get(p_val, 50.0)

    def _confidence_score(self, o: object) -> float:
        confidence = getattr(o, "confidence", None) or 0.85
        return float(confidence) * 100

    def _actionability_score(self, o: object) -> float:
        """50 base + 25 for specific action text + 25 for a deadline."""
        score = 50.0
        action = getattr(o, "action_required", "") or ""
        if len(action) > 20:
            score += 25.0
        if getattr(o, "deadline", None):
            score += 25.0
        return score

    def _relevance_score(self, o: object, profile: object) -> float:
        """
        Profile-aware relevance: penalizes rules that contradict profile facts.
        Returns 0–100. Rules with no matching profile trigger default to 70.
        """
        id_ = (getattr(o, "id", "") or "").lower()
        title_ = (getattr(o, "title", "") or "").lower()
        # Combined text for pattern matching (handles both snake_case ids and space-separated titles)
        combined_ = id_ + " " + title_.replace(" ", "_")

        def _bool(attr: str) -> bool:
            return bool(getattr(profile, attr, False))

        def _decimal(attr: str) -> Decimal:
            v = getattr(profile, attr, Decimal("0"))
            return Decimal(str(v)) if v else Decimal("0")

        def _match(*patterns: str) -> bool:
            return any(x in combined_ for x in patterns)

        # ── Rule-engine opportunities (re_* IDs): route by category ────────
        # Title patterns below won't match opaque rule IDs like re_ded046, so
        # we use the opportunity's category attribute directly.
        if id_.startswith("re_"):
            cat = getattr(o, "category", None)
            cat_val = (cat.value if cat and hasattr(cat, "value") else "").lower()
            if cat_val == "retirement":
                # Retirement is universally relevant; boost slightly if has IRA/401k balance
                return 85.0 if _decimal("ira_balance") > 0 else 78.0
            if cat_val == "investment":
                has_inv = (
                    _decimal("capital_gains") > 0 or _decimal("long_term_gains") > 0
                    or _decimal("short_term_gains") > 0 or _decimal("dividend_income") > 0
                    or _decimal("crypto_gains") > 0
                )
                return 82.0 if has_inv else 18.0
            if cat_val == "real_estate":
                has_re = _decimal("rental_income") > 0 or _bool("owns_home")
                return 82.0 if has_re else 12.0
            if cat_val == "business":
                has_biz = (
                    _decimal("self_employment_income") > 0
                    or _decimal("business_income") > 0
                    or _bool("has_business") or _bool("is_gig_worker")
                )
                return 82.0 if has_biz else 22.0
            if cat_val == "education":
                return 80.0 if (_bool("has_college_students") or _bool("has_529_plan")) else 18.0
            if cat_val == "healthcare":
                return 82.0 if _bool("has_hdhp") else 30.0
            if cat_val == "credit":
                return 68.0
            if cat_val == "deduction":
                return 62.0
            if cat_val == "timing":
                return 58.0
            if cat_val == "filing_status":
                return 60.0
            return 68.0  # unknown category

        # ── Foreign / international ────────────────────────────────────────
        if _match("foreign", "fbar", "pfic", "intl", "expat"):
            return 90.0 if _decimal("foreign_income") > 0 else 5.0

        # ── EV / clean vehicle ─────────────────────────────────────────────
        if _match("clean_vehicle", "ev_", "electric_vehicle", "ev purchase", "30d"):
            return 90.0 if _bool("has_ev_purchase") else 8.0

        # ── Solar / residential energy ─────────────────────────────────────
        if _match("solar", "residential_energy", "25d", "home_energy", "25c"):
            return 90.0 if (_bool("has_solar") or _bool("has_home_energy_improvements")) else 10.0

        # ── Rental income ──────────────────────────────────────────────────
        if _match("rental", "real_estate_prof", "passive_loss", "str_", "schedule_e"):
            if _decimal("rental_income") <= 0:
                return 8.0
            return 90.0 if _bool("rental_active_participation") else 60.0

        # ── Home office ────────────────────────────────────────────────────
        if _match("home_office", "business_use_of_home", "587", "home office"):
            return 88.0 if _bool("has_home_office") else 12.0

        # ── Mortgage / home ownership ──────────────────────────────────────
        if _match("mortgage", "home_interest", "936"):
            return 88.0 if _bool("owns_home") else 5.0

        # ── Children / dependent care ──────────────────────────────────────
        if _match("child_tax", "ctc", "dependent_care", "daycare", "child_care", "child_credit", "child tax"):
            if _bool("has_children_under_13"):
                return 90.0
            return 40.0 if _bool("has_children_under_17") else 5.0

        # ── College / education credits ────────────────────────────────────
        if _match("aotc", "lifetime_learning", "education_credit", "529"):
            if _bool("has_college_students"):
                return 85.0
            return 30.0 if _bool("has_529_plan") else 10.0

        # ── HSA ────────────────────────────────────────────────────────────
        if _match("hsa", "health_savings", "969"):
            return 90.0 if _bool("has_hdhp") else 5.0

        # ── ISO / equity compensation ──────────────────────────────────────
        if _match("iso_", "incentive_stock", "83b", "amt_iso"):
            return 88.0 if _bool("has_iso_options") else 5.0

        # ── RSU / ESPP ─────────────────────────────────────────────────────
        if _match("rsu", "espp", "restricted_stock"):
            return 85.0 if (_bool("has_rsu") or _bool("has_espp")) else 5.0

        # ── NUA ────────────────────────────────────────────────────────────
        if "nua" in id_ or "net_unrealized" in title_:
            return 5.0  # rare — employer stock in 401k only

        # ── QOZ / Opportunity Zone ─────────────────────────────────────────
        if _match("qoz", "opportunity_zone", "1400z"):
            return 90.0 if _bool("has_opportunity_zone_investment") else 5.0

        # ── QSBS §1202 ─────────────────────────────────────────────────────
        if _match("qsbs", "1202", "qualified_small_business"):
            return 5.0

        # ── Tax-loss harvesting / capital gains ────────────────────────────
        if _match("tax_loss", "harvest"):
            has_gains = (
                _decimal("capital_gains") > 0
                or _decimal("short_term_gains") > 0
                or _decimal("long_term_gains") > 0
            )
            return 90.0 if has_gains else 10.0

        # ── Crypto ────────────────────────────────────────────────────────
        if _match("crypto", "digital_asset", "bitcoin", "virtual_currency"):
            return 85.0 if _decimal("crypto_gains") > 0 else 8.0

        # ── Vehicle mileage ────────────────────────────────────────────────
        if _match("vehicle", "mileage", "auto_expense", "463"):
            return 88.0 if getattr(profile, "vehicle_business_miles", 0) > 0 else 5.0

        # ── Self-employment / SE income ────────────────────────────────────
        if _match("se_", "self_employ", "schedule_c", "qbi", "199a", "sep_ira", "solo_401k"):
            has_se = (
                _decimal("self_employment_income") > 0
                or _decimal("business_income") > 0
                or _bool("is_gig_worker")
            )
            return 88.0 if has_se else 5.0

        # ── Inherited IRA ──────────────────────────────────────────────────
        if _match("inherited_ira", "10_year_rule", "beneficiary_ira"):
            return 88.0 if _bool("has_inherited_ira") else 5.0

        # ── RMD ───────────────────────────────────────────────────────────
        if _match("rmd", "required_minimum"):
            age = getattr(profile, "age", 0) or 0
            return 90.0 if (age >= 73 or _decimal("rmd_amount") > 0) else 5.0

        # ── QCD ───────────────────────────────────────────────────────────
        if _match("qcd", "qualified_charitable_dist"):
            age = getattr(profile, "age", 0) or 0
            return 88.0 if (age >= 70 and _decimal("ira_balance") > 0) else 8.0

        # ── Social Security taxation ───────────────────────────────────────
        if _match("social_security", "ss_taxation", "provisional_income", "915"):
            return 85.0 if _decimal("social_security_income") > 0 else 5.0

        # ── NOL carryforward ──────────────────────────────────────────────
        if _match("nol", "net_operating_loss", "536"):
            return 88.0 if _bool("has_nol_carryforward") else 5.0

        # ── Donor-Advised Fund ─────────────────────────────────────────────
        if _match("daf", "donor_advised"):
            return 85.0 if _bool("has_donor_advised_fund") else 40.0

        # ── Gambling ──────────────────────────────────────────────────────
        if _match("gambling", "wagering"):
            return 80.0 if _decimal("gambling_winnings") > 0 else 5.0

        # ── Hobby income ──────────────────────────────────────────────────
        if _match("hobby", "activity_not_profit"):
            return 80.0 if _decimal("hobby_income") > 0 else 5.0

        # ── Household employee (nanny tax) ─────────────────────────────────
        if _match("household_employee", "nanny_tax", "schedule_h"):
            return 85.0 if _bool("has_household_employee") else 5.0

        # ── COD / insolvency ───────────────────────────────────────────────
        if _match("cancellation_of_debt", "cod_", "insolvency", "4681"):
            return 85.0 if _bool("has_cod_income") else 5.0

        # ── IRA-related (general) ──────────────────────────────────────────
        if _match("ira", "roth_conversion", "backdoor_roth"):
            return 85.0 if _decimal("ira_balance") > 0 else 60.0

        # ── NIIT ──────────────────────────────────────────────────────────
        if _match("niit", "net_investment_income", "8960"):
            investment = (
                _decimal("long_term_gains")
                + _decimal("short_term_gains")
                + _decimal("dividend_income")
                + _decimal("rental_income")
            )
            return 88.0 if investment > 0 else 5.0

        # ── IRMAA / Medicare ──────────────────────────────────────────────
        if _match("irmaa", "medicare_surcharge"):
            age = getattr(profile, "age", 0) or 0
            return 80.0 if age >= 63 else 5.0

        # ── Passive loss carryforward ──────────────────────────────────────
        if _match("passive_loss_carryfwd", "suspended_loss"):
            return 88.0 if _decimal("passive_losses_carryforward") > 0 else 5.0

        # ── Short-term rental ──────────────────────────────────────────────
        if _match("short_term_rental", "airbnb", "str_"):
            return 85.0 if getattr(profile, "str_rental_days", 0) > 0 else 5.0

        # Default: moderately relevant
        return 70.0


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_opportunity_scorer() -> OpportunityScorer:
    """Return the singleton OpportunityScorer instance."""
    return OpportunityScorer()
