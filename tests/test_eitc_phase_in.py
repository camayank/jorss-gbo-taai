"""
Tests for EITC phase-in calculation per IRS Pub. 596.
"""

import pytest
from calculator.tax_year_config import TaxYearConfig


class TestEitcPhaseInConfig:
    """Test EITC phase-in configuration exists in TaxYearConfig."""

    def test_config_has_phase_in_rate(self):
        """Config should have phase-in rates by number of children."""
        config = TaxYearConfig.for_2025()
        assert config.eitc_phase_in_rate is not None
        assert 0 in config.eitc_phase_in_rate
        assert 1 in config.eitc_phase_in_rate
        assert 2 in config.eitc_phase_in_rate
        assert 3 in config.eitc_phase_in_rate

    def test_config_has_phase_in_end(self):
        """Config should have phase-in end thresholds by children."""
        config = TaxYearConfig.for_2025()
        assert config.eitc_phase_in_end is not None
        assert 0 in config.eitc_phase_in_end
        assert 1 in config.eitc_phase_in_end
        assert 2 in config.eitc_phase_in_end
        assert 3 in config.eitc_phase_in_end

    def test_phase_in_rate_values_per_pub_596(self):
        """Phase-in rates should match IRS Pub. 596."""
        config = TaxYearConfig.for_2025()
        assert config.eitc_phase_in_rate[0] == pytest.approx(0.0765, rel=1e-4)
        assert config.eitc_phase_in_rate[1] == pytest.approx(0.34, rel=1e-4)
        assert config.eitc_phase_in_rate[2] == pytest.approx(0.40, rel=1e-4)
        assert config.eitc_phase_in_rate[3] == pytest.approx(0.45, rel=1e-4)

    def test_phase_in_end_values_per_pub_596(self):
        """Phase-in end thresholds should match IRS Pub. 596."""
        config = TaxYearConfig.for_2025()
        assert config.eitc_phase_in_end[0] == pytest.approx(8490.0, rel=1e-2)
        assert config.eitc_phase_in_end[1] == pytest.approx(12730.0, rel=1e-2)
        assert config.eitc_phase_in_end[2] == pytest.approx(17880.0, rel=1e-2)
        assert config.eitc_phase_in_end[3] == pytest.approx(17880.0, rel=1e-2)
