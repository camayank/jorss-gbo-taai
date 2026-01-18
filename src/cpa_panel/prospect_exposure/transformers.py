"""
Prospect Exposure Transformers

Pure functions that transform internal tax computation results
into prospect-safe exposure contracts.

DESIGN PRINCIPLES:
- Pure functions: No IO, no side effects, no state
- Exact → Directional: Never leak precise values
- Quantitative → Qualitative: Bands and categories only
- Fail safe: When in doubt, return UNKNOWN/UNCLEAR

RED LINE ENFORCEMENT:
These transformers are the ONLY path from internal data to prospect exposure.
Any attempt to bypass these transformers violates the 9 Red Lines.
"""

from typing import Any, Dict, List, Optional
from .contracts import (
    # Enums
    OutcomeType,
    AmountBand,
    ConfidenceBand,
    DisclaimerCode,
    ComplexityLevel,
    ComplexityReason,
    DriverCategory,
    DriverDirection,
    OpportunityCategory,
    OpportunitySeverity,
    ScenarioOutcomeShift,
    SummaryMessageCode,
    # Contracts
    ProspectOutcomeExposure,
    ProspectComplexityExposure,
    DriverItem,
    ProspectDriverExposure,
    OpportunityLabel,
    ProspectOpportunityExposure,
    ScenarioComparison,
    ProspectScenarioExposure,
    ProspectDiscoverySummary,
)


class OutcomeWrapper:
    """
    Transforms internal tax computation result to prospect-safe outcome.

    Input: Exact refund/owed amount, confidence percentage
    Output: Directional outcome, coarse band, qualitative confidence
    """

    # Band thresholds - these define the coarse bands
    BAND_THRESHOLDS = [
        (500, AmountBand.BAND_0_500),
        (2000, AmountBand.BAND_500_2K),
        (5000, AmountBand.BAND_2K_5K),
        (10000, AmountBand.BAND_5K_10K),
        (25000, AmountBand.BAND_10K_25K),
    ]

    @classmethod
    def transform(
        cls,
        refund_or_owed: Optional[float],
        confidence_pct: Optional[float] = None,
        data_completeness: Optional[float] = None,
    ) -> ProspectOutcomeExposure:
        """
        Transform exact amount to prospect-safe outcome.

        Args:
            refund_or_owed: Positive = refund, negative = owed, None = unknown
            confidence_pct: Internal confidence 0-100, None = unknown
            data_completeness: Data completeness 0-1, None = unknown

        Returns:
            ProspectOutcomeExposure with directional, banded values
        """
        # Determine outcome type
        outcome_type = cls._determine_outcome_type(refund_or_owed)

        # Determine amount band (always use absolute value)
        amount_band = cls._determine_amount_band(refund_or_owed)

        # Determine confidence band
        confidence_band = cls._determine_confidence_band(
            confidence_pct, data_completeness
        )

        # Default disclaimer
        disclaimer = DisclaimerCode.DISCOVERY_ONLY
        if confidence_band == ConfidenceBand.LOW:
            disclaimer = DisclaimerCode.PRELIMINARY_ESTIMATE

        return ProspectOutcomeExposure(
            outcome_type=outcome_type,
            amount_band=amount_band,
            confidence_band=confidence_band,
            disclaimer_code=disclaimer,
        )

    @classmethod
    def _determine_outcome_type(cls, amount: Optional[float]) -> OutcomeType:
        """Convert exact amount to directional outcome."""
        if amount is None:
            return OutcomeType.UNCLEAR

        # Use a threshold to avoid "LIKELY_REFUND" for $5
        threshold = 100
        if amount > threshold:
            return OutcomeType.LIKELY_REFUND
        elif amount < -threshold:
            return OutcomeType.LIKELY_OWED
        else:
            return OutcomeType.UNCLEAR

    @classmethod
    def _determine_amount_band(cls, amount: Optional[float]) -> AmountBand:
        """Convert exact amount to coarse band."""
        if amount is None:
            return AmountBand.UNKNOWN

        abs_amount = abs(amount)

        for threshold, band in cls.BAND_THRESHOLDS:
            if abs_amount <= threshold:
                return band

        return AmountBand.BAND_25K_PLUS

    @classmethod
    def _determine_confidence_band(
        cls,
        confidence_pct: Optional[float],
        data_completeness: Optional[float],
    ) -> ConfidenceBand:
        """Convert confidence percentage to qualitative band."""
        # If no confidence info, default to LOW
        if confidence_pct is None and data_completeness is None:
            return ConfidenceBand.LOW

        # Use whichever is available, preferring confidence_pct
        score = confidence_pct if confidence_pct is not None else (data_completeness * 100 if data_completeness else 0)

        if score >= 80:
            return ConfidenceBand.HIGH
        elif score >= 50:
            return ConfidenceBand.MEDIUM
        else:
            return ConfidenceBand.LOW


class ComplexityClassifier:
    """
    Transforms internal flags and metadata to prospect-safe complexity.

    Input: Various internal flags about tax situation
    Output: Simple/Moderate/Complex classification with up to 3 reasons
    """

    # Complexity indicators and their weights
    COMPLEXITY_INDICATORS = {
        'has_schedule_c': (ComplexityReason.SELF_EMPLOYMENT, 2),
        'has_schedule_e': (ComplexityReason.RENTAL_INCOME, 2),
        'has_virtual_currency': (ComplexityReason.CRYPTO_TRANSACTIONS, 2),
        'has_foreign_income': (ComplexityReason.FOREIGN_INCOME, 3),
        'has_k1': (ComplexityReason.K1_PARTNERSHIP, 2),
        'is_multi_state': (ComplexityReason.MULTI_STATE, 1),
        'is_high_income': (ComplexityReason.LARGE_INCOME, 1),
        'is_itemizing': (ComplexityReason.ITEMIZING, 1),
        'has_capital_gains': (ComplexityReason.CAPITAL_GAINS, 1),
        'has_business_entity': (ComplexityReason.BUSINESS_ENTITY, 2),
    }

    @classmethod
    def transform(
        cls,
        flags: Dict[str, bool],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProspectComplexityExposure:
        """
        Transform internal flags to prospect-safe complexity.

        Args:
            flags: Dict of boolean flags (has_schedule_c, has_k1, etc.)
            metadata: Optional additional metadata

        Returns:
            ProspectComplexityExposure with level and up to 3 reasons
        """
        # Collect reasons with weights
        weighted_reasons = []
        for flag_name, (reason, weight) in cls.COMPLEXITY_INDICATORS.items():
            if flags.get(flag_name, False):
                weighted_reasons.append((reason, weight))

        # Sort by weight descending and take top 3
        weighted_reasons.sort(key=lambda x: x[1], reverse=True)
        top_reasons = [r[0] for r in weighted_reasons[:3]]

        # Calculate total weight for level determination
        total_weight = sum(w for _, w in weighted_reasons)

        # Determine complexity level
        if total_weight >= 5:
            level = ComplexityLevel.COMPLEX
        elif total_weight >= 2:
            level = ComplexityLevel.MODERATE
        else:
            level = ComplexityLevel.SIMPLE

        return ProspectComplexityExposure(
            level=level,
            reasons=top_reasons,
        )


class DriverSanitizer:
    """
    Transforms internal tax drivers to prospect-safe driver exposure.

    Input: Detailed driver analysis with exact amounts
    Output: Top 3 drivers with category and direction only
    """

    # Map internal driver types to categories
    DRIVER_CATEGORY_MAP = {
        'wages': DriverCategory.INCOME_MIX,
        'w2_income': DriverCategory.INCOME_MIX,
        'self_employment': DriverCategory.BUSINESS_ACTIVITY,
        'business_income': DriverCategory.BUSINESS_ACTIVITY,
        'interest': DriverCategory.INCOME_MIX,
        'dividends': DriverCategory.INCOME_MIX,
        'capital_gains': DriverCategory.CAPITAL_GAINS,
        'rental_income': DriverCategory.INCOME_MIX,
        'withholding': DriverCategory.WITHHOLDING_PATTERN,
        'estimated_payments': DriverCategory.WITHHOLDING_PATTERN,
        'standard_deduction': DriverCategory.DEDUCTION_MIX,
        'itemized_deductions': DriverCategory.DEDUCTION_MIX,
        'mortgage_interest': DriverCategory.DEDUCTION_MIX,
        'charitable': DriverCategory.DEDUCTION_MIX,
        'retirement_contributions': DriverCategory.RETIREMENT_CONTRIBUTIONS,
        'ira_contributions': DriverCategory.RETIREMENT_CONTRIBUTIONS,
        '401k': DriverCategory.RETIREMENT_CONTRIBUTIONS,
        'child_tax_credit': DriverCategory.CREDIT_ELIGIBILITY,
        'eitc': DriverCategory.CREDIT_ELIGIBILITY,
        'education_credit': DriverCategory.CREDIT_ELIGIBILITY,
        'dependents': DriverCategory.DEPENDENT_SITUATION,
    }

    @classmethod
    def transform(
        cls,
        internal_drivers: List[Dict[str, Any]],
    ) -> ProspectDriverExposure:
        """
        Transform internal drivers to prospect-safe exposure.

        Args:
            internal_drivers: List of dicts with 'type', 'amount', 'impact'

        Returns:
            ProspectDriverExposure with top 3 drivers (category, rank, direction)
        """
        if not internal_drivers:
            return ProspectDriverExposure(top_drivers=[])

        # Sort by absolute impact and take top 3
        sorted_drivers = sorted(
            internal_drivers,
            key=lambda d: abs(d.get('impact', d.get('amount', 0))),
            reverse=True,
        )[:3]

        driver_items = []
        for rank, driver in enumerate(sorted_drivers, start=1):
            driver_type = driver.get('type', '').lower()
            category = cls.DRIVER_CATEGORY_MAP.get(
                driver_type, DriverCategory.INCOME_MIX
            )

            # Determine direction from impact
            impact = driver.get('impact', driver.get('amount', 0))
            if impact > 0:
                direction = DriverDirection.PUSHES_TOWARD_REFUND
            elif impact < 0:
                direction = DriverDirection.PUSHES_TOWARD_OWED
            else:
                direction = DriverDirection.NEUTRAL

            driver_items.append(DriverItem(
                category=category,
                rank=rank,
                direction=direction,
            ))

        return ProspectDriverExposure(top_drivers=driver_items)


class OpportunityLabeler:
    """
    Transforms internal opportunities to prospect-safe labels.

    Input: Detailed opportunity analysis with specific recommendations
    Output: Category labels with severity, max 3 visible
    """

    # Map internal opportunity types to categories
    OPPORTUNITY_CATEGORY_MAP = {
        'retirement_contribution': OpportunityCategory.RETIREMENT,
        'ira': OpportunityCategory.RETIREMENT,
        '401k': OpportunityCategory.RETIREMENT,
        'hsa': OpportunityCategory.HEALTH_SAVINGS,
        'fsa': OpportunityCategory.HEALTH_SAVINGS,
        'business_entity': OpportunityCategory.BUSINESS_STRUCTURE,
        's_corp': OpportunityCategory.BUSINESS_STRUCTURE,
        'llc': OpportunityCategory.BUSINESS_STRUCTURE,
        'charitable': OpportunityCategory.CHARITABLE,
        'donation': OpportunityCategory.CHARITABLE,
        'education': OpportunityCategory.EDUCATION,
        '529': OpportunityCategory.EDUCATION,
        'dependent': OpportunityCategory.DEPENDENTS,
        'child': OpportunityCategory.DEPENDENTS,
        'mortgage': OpportunityCategory.HOUSING,
        'home': OpportunityCategory.HOUSING,
        'investment': OpportunityCategory.INVESTMENT_TAX,
        'tax_loss': OpportunityCategory.INVESTMENT_TAX,
        'foreign': OpportunityCategory.FOREIGN_REPORTING,
        'fbar': OpportunityCategory.FOREIGN_REPORTING,
        'crypto': OpportunityCategory.CRYPTO_REPORTING,
        'virtual_currency': OpportunityCategory.CRYPTO_REPORTING,
        'state': OpportunityCategory.STATE_TAX,
    }

    @classmethod
    def transform(
        cls,
        internal_opportunities: List[Dict[str, Any]],
    ) -> ProspectOpportunityExposure:
        """
        Transform internal opportunities to prospect-safe labels.

        Args:
            internal_opportunities: List of opportunity dicts

        Returns:
            ProspectOpportunityExposure with total, visible (max 3), hidden count
        """
        if not internal_opportunities:
            return ProspectOpportunityExposure(
                total_flagged=0,
                visible=[],
                hidden_count=0,
            )

        total = len(internal_opportunities)

        # Sort by potential_savings or priority
        sorted_opps = sorted(
            internal_opportunities,
            key=lambda o: o.get('potential_savings', o.get('priority', 0)),
            reverse=True,
        )

        # Take top 3 for visibility
        visible_opps = sorted_opps[:3]
        hidden_count = max(0, total - 3)

        visible_labels = []
        for opp in visible_opps:
            opp_type = opp.get('type', opp.get('category', '')).lower()

            # Find matching category
            category = OpportunityCategory.OTHER
            for key, cat in cls.OPPORTUNITY_CATEGORY_MAP.items():
                if key in opp_type:
                    category = cat
                    break

            # Determine severity from potential_savings
            savings = opp.get('potential_savings', 0)
            if savings >= 5000:
                severity = OpportunitySeverity.HIGH
            elif savings >= 1000:
                severity = OpportunitySeverity.MEDIUM
            else:
                severity = OpportunitySeverity.LOW

            visible_labels.append(OpportunityLabel(
                category=category,
                severity=severity,
            ))

        return ProspectOpportunityExposure(
            total_flagged=total,
            visible=visible_labels,
            hidden_count=hidden_count,
        )


class ScenarioDirection:
    """
    Transforms internal scenario comparisons to prospect-safe exposure.

    Input: Detailed scenario analysis with exact amounts
    Output: Directional comparison (better/worse), max 2 scenarios
    """

    @classmethod
    def transform(
        cls,
        internal_scenarios: List[Dict[str, Any]],
    ) -> ProspectScenarioExposure:
        """
        Transform internal scenarios to prospect-safe directional comparisons.

        Args:
            internal_scenarios: List of scenario dicts with amounts

        Returns:
            ProspectScenarioExposure with max 2 comparisons
        """
        if not internal_scenarios:
            return ProspectScenarioExposure(comparisons=[])

        # Take only top 2 scenarios
        top_scenarios = internal_scenarios[:2]

        comparisons = []
        for scenario in top_scenarios:
            name = scenario.get('name', scenario.get('scenario_name', 'Alternative'))
            # Truncate name to 50 chars
            name = name[:50]

            # Determine direction from delta
            delta = scenario.get('delta', scenario.get('difference', 0))
            threshold = 100  # Ignore small differences

            if delta > threshold:
                shift = ScenarioOutcomeShift.BETTER
            elif delta < -threshold:
                shift = ScenarioOutcomeShift.WORSE
            elif delta is None:
                shift = ScenarioOutcomeShift.UNKNOWN
            else:
                shift = ScenarioOutcomeShift.NO_MEANINGFUL_CHANGE

            # Determine confidence from scenario data
            confidence = scenario.get('confidence', 0.5)
            if confidence >= 0.8:
                conf_band = ConfidenceBand.HIGH
            elif confidence >= 0.5:
                conf_band = ConfidenceBand.MEDIUM
            else:
                conf_band = ConfidenceBand.LOW

            comparisons.append(ScenarioComparison(
                scenario_name=name,
                outcome_shift=shift,
                confidence_band=conf_band,
            ))

        return ProspectScenarioExposure(comparisons=comparisons)


class ProspectExposureAssembler:
    """
    Assembles all transformed components into the final ProspectDiscoverySummary.

    This is the ONLY entry point for creating prospect-facing output.
    """

    @classmethod
    def compose(
        cls,
        outcome: ProspectOutcomeExposure,
        complexity: ProspectComplexityExposure,
        drivers: ProspectDriverExposure,
        opportunities: ProspectOpportunityExposure,
        scenarios: ProspectScenarioExposure,
    ) -> ProspectDiscoverySummary:
        """
        Compose all components into final summary.

        Args:
            outcome: Transformed outcome exposure
            complexity: Transformed complexity exposure
            drivers: Transformed driver exposure
            opportunities: Transformed opportunity exposure
            scenarios: Transformed scenario exposure

        Returns:
            ProspectDiscoverySummary ready for prospect-facing layer
        """
        # Determine summary message code based on complexity and opportunities
        message_code = cls._determine_message_code(complexity, opportunities)

        # Build disclaimer list
        disclaimers = cls._build_disclaimers(outcome, complexity)

        return ProspectDiscoverySummary(
            outcome=outcome,
            complexity=complexity,
            drivers=drivers,
            opportunities=opportunities,
            scenarios=scenarios,
            summary_message_code=message_code,
            disclaimers=disclaimers,
        )

    @classmethod
    def _determine_message_code(
        cls,
        complexity: ProspectComplexityExposure,
        opportunities: ProspectOpportunityExposure,
    ) -> SummaryMessageCode:
        """Determine appropriate pre-approved message code."""
        if complexity.level == ComplexityLevel.COMPLEX:
            return SummaryMessageCode.COMPLEX_SITUATION
        elif complexity.level == ComplexityLevel.MODERATE:
            if opportunities.total_flagged >= 3:
                return SummaryMessageCode.MULTIPLE_OPPORTUNITIES
            return SummaryMessageCode.MODERATE_COMPLEXITY
        else:
            if opportunities.total_flagged >= 2:
                return SummaryMessageCode.MULTIPLE_OPPORTUNITIES
            return SummaryMessageCode.STRAIGHTFORWARD_SITUATION

    @classmethod
    def _build_disclaimers(
        cls,
        outcome: ProspectOutcomeExposure,
        complexity: ProspectComplexityExposure,
    ) -> List[DisclaimerCode]:
        """Build list of applicable disclaimers."""
        disclaimers = [DisclaimerCode.NOT_TAX_ADVICE]

        if outcome.confidence_band == ConfidenceBand.LOW:
            disclaimers.append(DisclaimerCode.PRELIMINARY_ESTIMATE)

        if complexity.level == ComplexityLevel.COMPLEX:
            disclaimers.append(DisclaimerCode.SUBJECT_TO_CPA_REVIEW)

        disclaimers.append(DisclaimerCode.DISCOVERY_ONLY)

        return disclaimers
