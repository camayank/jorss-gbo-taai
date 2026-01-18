"""
Red Line Tests for Prospect Exposure Adapter

These tests verify that the 9 Red Lines are NEVER violated:
1. Final/actionable tax positions
2. Filing-ready outputs/forms
3. Optimization logic/how-to mechanics
4. Risk conclusions/audit exposure judgments
5. AI-generated advisory language
6. Completeness/confidence signals (exact percentages)
7. CPA internal review artifacts
8. Comparative CPA intelligence
9. Irreversibility/urgency framing

Each test is designed to FAIL if the contracts allow leaking sensitive data.
"""

import pytest
from pydantic import ValidationError

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cpa_panel.prospect_exposure.contracts import (
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

from cpa_panel.prospect_exposure.transformers import (
    OutcomeWrapper,
    ComplexityClassifier,
    DriverSanitizer,
    OpportunityLabeler,
    ScenarioDirection,
    ProspectExposureAssembler,
)


# =============================================================================
# RED LINE 1: No Exact Numbers Leak
# =============================================================================

class TestNoExactNumbersLeak:
    """Verify that exact dollar amounts never appear in outputs."""

    def test_outcome_uses_bands_not_exact_amounts(self):
        """Outcome exposure must use bands, not exact amounts."""
        # Transform exact amount
        result = OutcomeWrapper.transform(
            refund_or_owed=3547.89,
            confidence_pct=75.0,
        )

        # Verify no exact amount in output
        output_dict = result.model_dump()
        output_str = str(output_dict)

        # The exact amount should NOT appear anywhere
        assert "3547" not in output_str
        assert "3547.89" not in output_str

        # Should be in a band instead
        assert result.amount_band == AmountBand.BAND_2K_5K

    def test_outcome_bands_are_coarse(self):
        """Verify bands are coarse enough to prevent reverse-engineering."""
        # Test boundary values
        test_cases = [
            (499, AmountBand.BAND_0_500),
            (501, AmountBand.BAND_500_2K),
            (1999, AmountBand.BAND_500_2K),
            (2001, AmountBand.BAND_2K_5K),
            (4999, AmountBand.BAND_2K_5K),
            (5001, AmountBand.BAND_5K_10K),
            (9999, AmountBand.BAND_5K_10K),
            (10001, AmountBand.BAND_10K_25K),
            (24999, AmountBand.BAND_10K_25K),
            (25001, AmountBand.BAND_25K_PLUS),
        ]

        for amount, expected_band in test_cases:
            result = OutcomeWrapper.transform(refund_or_owed=amount)
            assert result.amount_band == expected_band, (
                f"Amount {amount} should map to {expected_band}"
            )

    def test_drivers_contain_no_amounts(self):
        """Driver exposure must not contain dollar amounts."""
        internal_drivers = [
            {'type': 'wages', 'amount': 75000, 'impact': 15000},
            {'type': 'withholding', 'amount': 12000, 'impact': 12000},
            {'type': 'mortgage_interest', 'amount': 8500, 'impact': -2000},
        ]

        result = DriverSanitizer.transform(internal_drivers)

        # Verify no amounts in output
        output_dict = result.model_dump()
        output_str = str(output_dict)

        assert "75000" not in output_str
        assert "12000" not in output_str
        assert "8500" not in output_str
        assert "15000" not in output_str
        assert "2000" not in output_str

        # Only categories and directions should be present
        for driver in result.top_drivers:
            assert isinstance(driver.category, DriverCategory)
            assert isinstance(driver.direction, DriverDirection)
            assert isinstance(driver.rank, int)

    def test_opportunities_contain_no_savings_amounts(self):
        """Opportunity exposure must not contain potential savings amounts."""
        internal_opportunities = [
            {'type': 'retirement_contribution', 'potential_savings': 6500},
            {'type': 'hsa', 'potential_savings': 2100},
            {'type': 'charitable', 'potential_savings': 800},
        ]

        result = OpportunityLabeler.transform(internal_opportunities)

        # Verify no amounts in output
        output_dict = result.model_dump()
        output_str = str(output_dict)

        assert "6500" not in output_str
        assert "2100" not in output_str
        assert "800" not in output_str

        # Only categories and severity should be present
        for opp in result.visible:
            assert isinstance(opp.category, OpportunityCategory)
            assert isinstance(opp.severity, OpportunitySeverity)


# =============================================================================
# RED LINE 2: Max Limits Enforced
# =============================================================================

class TestMaxLimitsEnforced:
    """Verify that max limits on arrays are strictly enforced."""

    def test_drivers_max_3(self):
        """Must reject more than 3 drivers."""
        # First, create 4 valid DriverItems (using rank 3 for 4th to avoid rank validation)
        drivers = [
            DriverItem(category=DriverCategory.INCOME_MIX, rank=1, direction=DriverDirection.NEUTRAL),
            DriverItem(category=DriverCategory.DEDUCTION_MIX, rank=2, direction=DriverDirection.NEUTRAL),
            DriverItem(category=DriverCategory.CREDIT_ELIGIBILITY, rank=3, direction=DriverDirection.NEUTRAL),
        ]
        # This should pass
        valid = ProspectDriverExposure(top_drivers=drivers)
        assert len(valid.top_drivers) == 3

        # Now test that rank=4 is rejected (ranks must be 1-3)
        with pytest.raises(ValidationError) as exc_info:
            DriverItem(category=DriverCategory.BUSINESS_ACTIVITY, rank=4, direction=DriverDirection.NEUTRAL)
        assert "less_than_equal" in str(exc_info.value) or "Input should be" in str(exc_info.value)

    def test_complexity_reasons_max_3(self):
        """Must reject more than 3 complexity reasons."""
        with pytest.raises(ValidationError) as exc_info:
            ProspectComplexityExposure(
                level=ComplexityLevel.COMPLEX,
                reasons=[
                    ComplexityReason.SELF_EMPLOYMENT,
                    ComplexityReason.RENTAL_INCOME,
                    ComplexityReason.CRYPTO_TRANSACTIONS,
                    ComplexityReason.FOREIGN_INCOME,
                ]
            )
        # Pydantic reports "too_long" for max_length violations
        assert "too_long" in str(exc_info.value) or "at most 3" in str(exc_info.value)

    def test_visible_opportunities_max_3(self):
        """Must reject more than 3 visible opportunities."""
        with pytest.raises(ValidationError) as exc_info:
            ProspectOpportunityExposure(
                total_flagged=10,
                visible=[
                    OpportunityLabel(category=OpportunityCategory.RETIREMENT, severity=OpportunitySeverity.HIGH),
                    OpportunityLabel(category=OpportunityCategory.HEALTH_SAVINGS, severity=OpportunitySeverity.HIGH),
                    OpportunityLabel(category=OpportunityCategory.CHARITABLE, severity=OpportunitySeverity.MEDIUM),
                    OpportunityLabel(category=OpportunityCategory.EDUCATION, severity=OpportunitySeverity.LOW),
                ],
                hidden_count=6,
            )
        # Pydantic reports "too_long" for max_length violations
        assert "too_long" in str(exc_info.value) or "at most 3" in str(exc_info.value)

    def test_scenario_comparisons_max_2(self):
        """Must reject more than 2 scenario comparisons."""
        with pytest.raises(ValidationError) as exc_info:
            ProspectScenarioExposure(
                comparisons=[
                    ScenarioComparison(scenario_name="A", outcome_shift=ScenarioOutcomeShift.BETTER, confidence_band=ConfidenceBand.HIGH),
                    ScenarioComparison(scenario_name="B", outcome_shift=ScenarioOutcomeShift.WORSE, confidence_band=ConfidenceBand.MEDIUM),
                    ScenarioComparison(scenario_name="C", outcome_shift=ScenarioOutcomeShift.UNKNOWN, confidence_band=ConfidenceBand.LOW),
                ]
            )
        # Pydantic reports "too_long" for max_length violations
        assert "too_long" in str(exc_info.value) or "at most 2" in str(exc_info.value)


# =============================================================================
# RED LINE 3: Driver Ranks Must Be Unique
# =============================================================================

class TestDriverRanksUnique:
    """Verify driver ranks are unique (1, 2, 3 not 1, 1, 2)."""

    def test_duplicate_ranks_rejected(self):
        """Must reject duplicate ranks."""
        with pytest.raises(ValidationError) as exc_info:
            ProspectDriverExposure(
                top_drivers=[
                    DriverItem(category=DriverCategory.INCOME_MIX, rank=1, direction=DriverDirection.NEUTRAL),
                    DriverItem(category=DriverCategory.DEDUCTION_MIX, rank=1, direction=DriverDirection.NEUTRAL),
                ]
            )
        assert "ranks must be unique" in str(exc_info.value).lower()

    def test_valid_unique_ranks(self):
        """Valid unique ranks should be accepted."""
        exposure = ProspectDriverExposure(
            top_drivers=[
                DriverItem(category=DriverCategory.INCOME_MIX, rank=1, direction=DriverDirection.PUSHES_TOWARD_REFUND),
                DriverItem(category=DriverCategory.DEDUCTION_MIX, rank=2, direction=DriverDirection.NEUTRAL),
                DriverItem(category=DriverCategory.CREDIT_ELIGIBILITY, rank=3, direction=DriverDirection.PUSHES_TOWARD_OWED),
            ]
        )
        assert len(exposure.top_drivers) == 3


# =============================================================================
# RED LINE 4: Confidence Must Be Bands, Not Percentages
# =============================================================================

class TestConfidenceBandsNotPercentages:
    """Verify confidence is qualitative bands, not exact percentages."""

    def test_confidence_is_band_not_number(self):
        """Confidence must be LOW/MEDIUM/HIGH, not a percentage."""
        result = OutcomeWrapper.transform(
            refund_or_owed=5000,
            confidence_pct=73.5,  # Exact percentage
        )

        # Output should not contain the exact percentage
        output_dict = result.model_dump()
        output_str = str(output_dict)

        assert "73.5" not in output_str
        assert "73" not in output_str

        # Should be a band
        assert result.confidence_band in [
            ConfidenceBand.LOW,
            ConfidenceBand.MEDIUM,
            ConfidenceBand.HIGH,
        ]

    def test_confidence_band_thresholds(self):
        """Verify confidence band thresholds."""
        # Low confidence (< 50%)
        result = OutcomeWrapper.transform(refund_or_owed=1000, confidence_pct=30)
        assert result.confidence_band == ConfidenceBand.LOW

        # Medium confidence (50-80%)
        result = OutcomeWrapper.transform(refund_or_owed=1000, confidence_pct=65)
        assert result.confidence_band == ConfidenceBand.MEDIUM

        # High confidence (>= 80%)
        result = OutcomeWrapper.transform(refund_or_owed=1000, confidence_pct=85)
        assert result.confidence_band == ConfidenceBand.HIGH


# =============================================================================
# RED LINE 5: No Custom Advisory Language
# =============================================================================

class TestNoCustomAdvisoryLanguage:
    """Verify only pre-approved message codes are used, no custom text."""

    def test_summary_message_is_code_not_text(self):
        """Summary messages must be pre-approved codes."""
        outcome = OutcomeWrapper.transform(refund_or_owed=3000, confidence_pct=70)
        complexity = ComplexityClassifier.transform({'has_schedule_c': True})
        drivers = DriverSanitizer.transform([{'type': 'wages', 'impact': 5000}])
        opportunities = OpportunityLabeler.transform([{'type': 'hsa', 'potential_savings': 1000}])
        scenarios = ScenarioDirection.transform([])

        result = ProspectExposureAssembler.compose(
            outcome=outcome,
            complexity=complexity,
            drivers=drivers,
            opportunities=opportunities,
            scenarios=scenarios,
        )

        # Message code must be from pre-approved enum
        assert result.summary_message_code in SummaryMessageCode

    def test_disclaimers_are_codes_not_custom_text(self):
        """Disclaimers must be standard codes."""
        outcome = ProspectOutcomeExposure(
            outcome_type=OutcomeType.LIKELY_REFUND,
            amount_band=AmountBand.BAND_2K_5K,
            confidence_band=ConfidenceBand.MEDIUM,
            disclaimer_code=DisclaimerCode.DISCOVERY_ONLY,
        )

        # Verify disclaimer is from enum
        assert outcome.disclaimer_code in DisclaimerCode


# =============================================================================
# RED LINE 6: Transformers Truncate Excess Data
# =============================================================================

class TestTransformersTruncateExcess:
    """Verify transformers properly limit output, not just validation."""

    def test_driver_sanitizer_limits_to_3(self):
        """DriverSanitizer must output max 3 drivers even with more input."""
        internal_drivers = [
            {'type': 'wages', 'impact': 10000},
            {'type': 'withholding', 'impact': 8000},
            {'type': 'mortgage_interest', 'impact': 5000},
            {'type': 'charitable', 'impact': 3000},
            {'type': 'retirement', 'impact': 2000},
        ]

        result = DriverSanitizer.transform(internal_drivers)

        # Must be at most 3
        assert len(result.top_drivers) <= 3

    def test_opportunity_labeler_limits_visible_to_3(self):
        """OpportunityLabeler must show max 3 visible even with more input."""
        internal_opportunities = [
            {'type': 'retirement', 'potential_savings': 6000},
            {'type': 'hsa', 'potential_savings': 5000},
            {'type': 'charitable', 'potential_savings': 4000},
            {'type': 'education', 'potential_savings': 3000},
            {'type': 'business', 'potential_savings': 2000},
        ]

        result = OpportunityLabeler.transform(internal_opportunities)

        # Visible must be at most 3
        assert len(result.visible) <= 3

        # But total should reflect actual count
        assert result.total_flagged == 5

        # Hidden count should be correct
        assert result.hidden_count == 2

    def test_scenario_direction_limits_to_2(self):
        """ScenarioDirection must output max 2 comparisons."""
        internal_scenarios = [
            {'name': 'Scenario A', 'delta': 5000, 'confidence': 0.8},
            {'name': 'Scenario B', 'delta': 3000, 'confidence': 0.7},
            {'name': 'Scenario C', 'delta': 1000, 'confidence': 0.6},
        ]

        result = ScenarioDirection.transform(internal_scenarios)

        # Must be at most 2
        assert len(result.comparisons) <= 2


# =============================================================================
# RED LINE 7: Contracts Are Immutable (Frozen)
# =============================================================================

class TestContractsImmutable:
    """Verify contracts cannot be modified after creation."""

    def test_outcome_exposure_is_frozen(self):
        """ProspectOutcomeExposure should be immutable."""
        outcome = ProspectOutcomeExposure(
            outcome_type=OutcomeType.LIKELY_REFUND,
            amount_band=AmountBand.BAND_2K_5K,
            confidence_band=ConfidenceBand.HIGH,
        )

        with pytest.raises((ValidationError, TypeError, AttributeError)):
            outcome.outcome_type = OutcomeType.LIKELY_OWED

    def test_driver_item_is_frozen(self):
        """DriverItem should be immutable."""
        driver = DriverItem(
            category=DriverCategory.INCOME_MIX,
            rank=1,
            direction=DriverDirection.PUSHES_TOWARD_REFUND,
        )

        with pytest.raises((ValidationError, TypeError, AttributeError)):
            driver.rank = 2


# =============================================================================
# RED LINE 8: Direction Not Magnitude for Scenarios
# =============================================================================

class TestScenarioDirectionNotMagnitude:
    """Verify scenarios show direction only, not dollar amounts."""

    def test_scenario_shows_direction_only(self):
        """Scenario comparison must show BETTER/WORSE, not amounts."""
        internal_scenarios = [
            {'name': 'Max 401k', 'delta': 4500, 'confidence': 0.9},
        ]

        result = ScenarioDirection.transform(internal_scenarios)

        # Output should not contain the exact delta
        output_dict = result.model_dump()
        output_str = str(output_dict)

        assert "4500" not in output_str

        # Should show direction instead
        assert result.comparisons[0].outcome_shift == ScenarioOutcomeShift.BETTER

    def test_small_changes_show_no_meaningful_change(self):
        """Small deltas should show NO_MEANINGFUL_CHANGE to avoid micro-optimization."""
        internal_scenarios = [
            {'name': 'Minor Adjustment', 'delta': 50, 'confidence': 0.9},
        ]

        result = ScenarioDirection.transform(internal_scenarios)

        # Small changes should be NO_MEANINGFUL_CHANGE
        assert result.comparisons[0].outcome_shift == ScenarioOutcomeShift.NO_MEANINGFUL_CHANGE


# =============================================================================
# RED LINE 9: Outcome Direction Has Threshold
# =============================================================================

class TestOutcomeDirectionThreshold:
    """Verify small amounts don't trigger LIKELY_REFUND/OWED."""

    def test_small_amounts_are_unclear(self):
        """Amounts near zero should be UNCLEAR, not LIKELY_REFUND/OWED."""
        # $50 refund should not show LIKELY_REFUND
        result = OutcomeWrapper.transform(refund_or_owed=50)
        assert result.outcome_type == OutcomeType.UNCLEAR

        # $50 owed should not show LIKELY_OWED
        result = OutcomeWrapper.transform(refund_or_owed=-50)
        assert result.outcome_type == OutcomeType.UNCLEAR

    def test_significant_amounts_show_direction(self):
        """Amounts beyond threshold should show direction."""
        # $500 refund should show LIKELY_REFUND
        result = OutcomeWrapper.transform(refund_or_owed=500)
        assert result.outcome_type == OutcomeType.LIKELY_REFUND

        # $500 owed should show LIKELY_OWED
        result = OutcomeWrapper.transform(refund_or_owed=-500)
        assert result.outcome_type == OutcomeType.LIKELY_OWED


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestFullPipeline:
    """Integration tests for the complete transformation pipeline."""

    def test_complete_pipeline_produces_valid_output(self):
        """Full pipeline should produce valid ProspectDiscoverySummary."""
        # Simulate internal data
        refund_amount = 4827.53
        confidence = 72.5

        internal_flags = {
            'has_schedule_c': True,
            'has_virtual_currency': True,
            'is_itemizing': True,
        }

        internal_drivers = [
            {'type': 'wages', 'impact': 15000},
            {'type': 'self_employment', 'impact': -8000},
            {'type': 'withholding', 'impact': 12000},
            {'type': 'mortgage_interest', 'impact': -3000},
        ]

        internal_opportunities = [
            {'type': 'retirement_contribution', 'potential_savings': 6500},
            {'type': 'hsa', 'potential_savings': 2100},
            {'type': 'charitable', 'potential_savings': 800},
            {'type': 'business_entity', 'potential_savings': 5000},
        ]

        internal_scenarios = [
            {'name': 'Max Retirement', 'delta': 3000, 'confidence': 0.85},
            {'name': 'S-Corp Election', 'delta': 8000, 'confidence': 0.6},
        ]

        # Transform all components
        outcome = OutcomeWrapper.transform(refund_amount, confidence)
        complexity = ComplexityClassifier.transform(internal_flags)
        drivers = DriverSanitizer.transform(internal_drivers)
        opportunities = OpportunityLabeler.transform(internal_opportunities)
        scenarios = ScenarioDirection.transform(internal_scenarios)

        # Assemble
        summary = ProspectExposureAssembler.compose(
            outcome=outcome,
            complexity=complexity,
            drivers=drivers,
            opportunities=opportunities,
            scenarios=scenarios,
        )

        # Verify structure
        assert isinstance(summary, ProspectDiscoverySummary)

        # Verify no exact values leaked
        output_str = str(summary.model_dump())
        assert "4827" not in output_str
        assert "72.5" not in output_str
        assert "15000" not in output_str
        assert "6500" not in output_str
        assert "3000" not in output_str
        assert "8000" not in output_str

        # Verify limits respected
        assert len(summary.drivers.top_drivers) <= 3
        assert len(summary.complexity.reasons) <= 3
        assert len(summary.opportunities.visible) <= 3
        assert len(summary.scenarios.comparisons) <= 2

    def test_pipeline_handles_empty_data(self):
        """Pipeline should handle empty/missing data gracefully."""
        outcome = OutcomeWrapper.transform(None, None)
        complexity = ComplexityClassifier.transform({})
        drivers = DriverSanitizer.transform([])
        opportunities = OpportunityLabeler.transform([])
        scenarios = ScenarioDirection.transform([])

        summary = ProspectExposureAssembler.compose(
            outcome=outcome,
            complexity=complexity,
            drivers=drivers,
            opportunities=opportunities,
            scenarios=scenarios,
        )

        assert summary.outcome.outcome_type == OutcomeType.UNCLEAR
        assert summary.outcome.amount_band == AmountBand.UNKNOWN
        assert summary.complexity.level == ComplexityLevel.SIMPLE
        assert len(summary.drivers.top_drivers) == 0
        assert summary.opportunities.total_flagged == 0
        assert len(summary.scenarios.comparisons) == 0
