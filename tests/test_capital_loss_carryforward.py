"""
Tests for Capital Loss Carryforward (IRC Sections 1211/1212)

Tests cover:
- Net gain position (no loss deduction, no carryforward)
- Loss under $3,000 limit (full deduction, no carryforward)
- Loss over $3,000 limit (creates carryforward)
- MFS $1,500 limit
- Carryforward character preservation (ST vs LT)
- Netting rules (ST vs LT offsetting)
- K-1 integration
- Crypto integration
- Engine integration
"""

import pytest
from src.models.income import Income, ScheduleK1, K1SourceType, VirtualCurrencyTransaction, VirtualCurrencyTransactionType
from src.calculator.engine import FederalTaxEngine
from src.calculator.tax_year_config import TaxYearConfig
from src.models.tax_return import TaxReturn
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.deductions import Deductions
from src.models.credits import TaxCredits


class TestNetGainPosition:
    """Tests for net gain scenarios (no loss deduction)."""

    def test_net_gain_no_carryforward(self):
        """When net position is gain, no loss deduction or carryforward."""
        income = Income(
            short_term_capital_gains=5000.0,
            long_term_capital_gains=10000.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        assert net_gain == 15000.0
        assert loss_ded == 0.0
        assert st_cf == 0.0
        assert lt_cf == 0.0
        assert net_st == 5000.0
        assert net_lt == 10000.0

    def test_st_loss_offset_by_lt_gain(self):
        """ST loss fully offset by LT gain results in net gain."""
        income = Income(
            short_term_capital_gains=0.0,
            long_term_capital_gains=10000.0,
            short_term_loss_carryforward=3000.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        # Net: -3000 + 10000 = +7000
        assert net_gain == 7000.0
        assert loss_ded == 0.0
        assert st_cf == 0.0
        assert lt_cf == 0.0

    def test_lt_loss_offset_by_st_gain(self):
        """LT loss fully offset by ST gain results in net gain."""
        income = Income(
            short_term_capital_gains=8000.0,
            long_term_capital_gains=0.0,
            long_term_loss_carryforward=5000.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        # Net: 8000 + (-5000) = +3000
        assert net_gain == 3000.0
        assert loss_ded == 0.0
        assert st_cf == 0.0
        assert lt_cf == 0.0


class TestLossUnderLimit:
    """Tests for losses under the $3,000 limit."""

    def test_small_loss_full_deduction(self):
        """Loss under $3,000 - full deduction, no carryforward."""
        income = Income(
            short_term_capital_gains=0.0,
            long_term_capital_gains=0.0,
            short_term_loss_carryforward=2000.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        assert net_gain == 0.0
        assert loss_ded == 2000.0
        assert st_cf == 0.0
        assert lt_cf == 0.0

    def test_exactly_3000_loss(self):
        """Loss exactly $3,000 - full deduction, no carryforward."""
        income = Income(
            short_term_capital_gains=0.0,
            long_term_capital_gains=0.0,
            long_term_loss_carryforward=3000.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        assert net_gain == 0.0
        assert loss_ded == 3000.0
        assert st_cf == 0.0
        assert lt_cf == 0.0

    def test_small_st_and_lt_losses(self):
        """Combined small ST and LT losses under limit."""
        income = Income(
            short_term_capital_gains=0.0,
            long_term_capital_gains=0.0,
            short_term_loss_carryforward=1000.0,
            long_term_loss_carryforward=1500.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        # Total loss: 2500, under 3000 limit
        assert net_gain == 0.0
        assert loss_ded == 2500.0
        assert st_cf == 0.0
        assert lt_cf == 0.0


class TestLossOverLimit:
    """Tests for losses over the $3,000 limit (creates carryforward)."""

    def test_lt_loss_over_limit(self):
        """LT loss over $3,000 creates LT carryforward."""
        income = Income(
            short_term_capital_gains=0.0,
            long_term_capital_gains=0.0,
            long_term_loss_carryforward=10000.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        assert net_gain == 0.0
        assert loss_ded == 3000.0
        assert st_cf == 0.0
        assert lt_cf == 7000.0  # 10000 - 3000

    def test_st_loss_over_limit(self):
        """ST loss over $3,000 creates ST carryforward."""
        income = Income(
            short_term_capital_gains=0.0,
            long_term_capital_gains=0.0,
            short_term_loss_carryforward=8000.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        assert net_gain == 0.0
        assert loss_ded == 3000.0
        assert st_cf == 5000.0  # 8000 - 3000
        assert lt_cf == 0.0

    def test_large_loss_carryforward(self):
        """Very large loss creates substantial carryforward."""
        income = Income(
            short_term_capital_gains=0.0,
            long_term_capital_gains=0.0,
            long_term_loss_carryforward=50000.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        assert net_gain == 0.0
        assert loss_ded == 3000.0
        assert st_cf == 0.0
        assert lt_cf == 47000.0


class TestMFSLimit:
    """Tests for Married Filing Separately $1,500 limit."""

    def test_mfs_limit_1500(self):
        """MFS limited to $1,500 annual deduction."""
        income = Income(
            short_term_capital_gains=0.0,
            long_term_capital_gains=0.0,
            short_term_loss_carryforward=5000.0,
        )
        result = income.calculate_net_capital_gain_loss("married_separate")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        assert loss_ded == 1500.0
        assert st_cf == 3500.0  # 5000 - 1500

    def test_mfs_small_loss_full_deduction(self):
        """MFS with loss under $1,500 gets full deduction."""
        income = Income(
            short_term_capital_gains=0.0,
            long_term_capital_gains=0.0,
            long_term_loss_carryforward=1000.0,
        )
        result = income.calculate_net_capital_gain_loss("married_separate")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        assert loss_ded == 1000.0
        assert st_cf == 0.0
        assert lt_cf == 0.0

    def test_mfj_gets_full_3000_limit(self):
        """MFJ gets full $3,000 limit."""
        income = Income(
            short_term_capital_gains=0.0,
            long_term_capital_gains=0.0,
            long_term_loss_carryforward=5000.0,
        )
        result = income.calculate_net_capital_gain_loss("married_joint")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        assert loss_ded == 3000.0
        assert lt_cf == 2000.0


class TestCarryforwardCharacter:
    """Tests for carryforward character preservation (ST vs LT)."""

    def test_st_only_loss_maintains_st_character(self):
        """Short-term only loss carryforward stays short-term."""
        income = Income(
            short_term_capital_gains=0.0,
            long_term_capital_gains=0.0,
            short_term_loss_carryforward=8000.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        _, _, st_cf, lt_cf, _, _ = result

        assert st_cf == 5000.0  # 8000 - 3000
        assert lt_cf == 0.0

    def test_lt_only_loss_maintains_lt_character(self):
        """Long-term only loss carryforward stays long-term."""
        income = Income(
            short_term_capital_gains=0.0,
            long_term_capital_gains=0.0,
            long_term_loss_carryforward=8000.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        _, _, st_cf, lt_cf, _, _ = result

        assert st_cf == 0.0
        assert lt_cf == 5000.0  # 8000 - 3000

    def test_mixed_losses_st_absorbs_limit_first(self):
        """When both ST and LT are losses, ST absorbs limit first."""
        income = Income(
            short_term_capital_gains=0.0,
            long_term_capital_gains=0.0,
            short_term_loss_carryforward=4000.0,
            long_term_loss_carryforward=4000.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        _, loss_ded, st_cf, lt_cf, _, _ = result

        # Total loss: 8000, limit: 3000
        # ST: 4000, absorbs 3000 of limit, 1000 remaining
        # LT: 4000, all carries forward
        assert loss_ded == 3000.0
        assert st_cf == 1000.0  # 4000 - 3000
        assert lt_cf == 4000.0

    def test_st_less_than_limit_lt_makes_up_difference(self):
        """When ST < limit, LT fills remaining limit."""
        income = Income(
            short_term_capital_gains=0.0,
            long_term_capital_gains=0.0,
            short_term_loss_carryforward=1000.0,
            long_term_loss_carryforward=5000.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        _, loss_ded, st_cf, lt_cf, _, _ = result

        # Total loss: 6000, limit: 3000
        # ST: 1000, fully used
        # LT: 5000, 2000 used for limit, 3000 carries forward
        assert loss_ded == 3000.0
        assert st_cf == 0.0
        assert lt_cf == 3000.0  # 5000 - 2000


class TestNettingRules:
    """Tests for capital gain/loss netting rules."""

    def test_st_gain_lt_loss_partial_offset(self):
        """ST gain partially offsets LT loss."""
        income = Income(
            short_term_capital_gains=2000.0,
            long_term_capital_gains=0.0,
            long_term_loss_carryforward=7000.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        # Net ST: +2000, Net LT: -7000
        # Overall: -5000
        assert net_st == 2000.0
        assert net_lt == -7000.0
        assert net_gain == 0.0
        assert loss_ded == 3000.0
        assert lt_cf == 2000.0  # 5000 - 3000 all from LT

    def test_lt_gain_st_loss_partial_offset(self):
        """LT gain partially offsets ST loss."""
        income = Income(
            short_term_capital_gains=0.0,
            long_term_capital_gains=4000.0,
            short_term_loss_carryforward=10000.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        # Net ST: -10000, Net LT: +4000
        # Overall: -6000
        assert net_st == -10000.0
        assert net_lt == 4000.0
        assert net_gain == 0.0
        assert loss_ded == 3000.0
        assert st_cf == 3000.0  # 6000 - 3000 all from ST

    def test_gains_and_losses_both_categories(self):
        """Both categories have gains and losses."""
        income = Income(
            short_term_capital_gains=3000.0,
            long_term_capital_gains=2000.0,
            short_term_loss_carryforward=5000.0,
            long_term_loss_carryforward=4000.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        # Net ST: 3000 - 5000 = -2000
        # Net LT: 2000 - 4000 = -2000
        # Overall: -4000
        assert net_st == -2000.0
        assert net_lt == -2000.0
        assert net_gain == 0.0
        assert loss_ded == 3000.0
        # Both are losses, ST absorbs limit first
        # ST: 2000, all absorbed by limit
        # LT: 2000, (3000-2000)=1000 absorbed by limit, 1000 carries forward
        assert st_cf == 0.0
        assert lt_cf == 1000.0


class TestK1Integration:
    """Tests for K-1 pass-through capital gains/losses."""

    def test_k1_gain_added(self):
        """K-1 capital gains are included."""
        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="Test Partnership",
            net_short_term_capital_gain=2000.0,
            net_long_term_capital_gain=5000.0,
        )
        income = Income(
            schedule_k1_forms=[k1],
            short_term_capital_gains=1000.0,
            long_term_capital_gains=3000.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, _, _, _, net_st, net_lt = result

        # ST: 1000 + 2000 = 3000
        # LT: 3000 + 5000 = 8000
        assert net_st == 3000.0
        assert net_lt == 8000.0
        assert net_gain == 11000.0

    def test_k1_loss_flows_through(self):
        """K-1 capital losses (negative values) are included."""
        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="Test Partnership",
            net_short_term_capital_gain=-4000.0,  # Loss
            net_long_term_capital_gain=1000.0,
        )
        income = Income(
            schedule_k1_forms=[k1],
            short_term_capital_gains=0.0,
            long_term_capital_gains=0.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        assert net_st == -4000.0
        assert net_lt == 1000.0
        # Overall: -3000, exactly at limit
        assert loss_ded == 3000.0
        assert st_cf == 0.0
        assert lt_cf == 0.0

    def test_k1_section_1231_gain(self):
        """Section 1231 gains from K-1 included as long-term."""
        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="Test Partnership",
            net_long_term_capital_gain=0.0,
            net_section_1231_gain=5000.0,
        )
        income = Income(
            schedule_k1_forms=[k1],
        )
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, _, _, _, _, net_lt = result

        assert net_lt == 5000.0
        assert net_gain == 5000.0


class TestCryptoIntegration:
    """Tests for crypto capital gains/losses integration."""

    def test_crypto_gains_included(self):
        """Crypto capital gains are included."""
        income = Income(
            virtual_currency_transactions=[
                VirtualCurrencyTransaction(
                    transaction_type=VirtualCurrencyTransactionType.SALE,
                    asset_name="Bitcoin",
                    quantity=1.0,
                    cost_basis=5000.0,
                    proceeds=8000.0,  # $3000 gain
                    is_long_term=True,
                )
            ]
        )
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, _, _, _, _, net_lt = result

        assert net_lt == 3000.0
        assert net_gain == 3000.0

    def test_crypto_losses_included(self):
        """Crypto capital losses are included."""
        income = Income(
            virtual_currency_transactions=[
                VirtualCurrencyTransaction(
                    transaction_type=VirtualCurrencyTransactionType.SALE,
                    asset_name="Bitcoin",
                    quantity=1.0,
                    cost_basis=10000.0,
                    proceeds=4000.0,  # $6000 loss
                    is_long_term=True,
                )
            ]
        )
        result = income.calculate_net_capital_gain_loss("single")
        _, loss_ded, _, lt_cf, _, net_lt = result

        assert net_lt == -6000.0
        assert loss_ded == 3000.0
        assert lt_cf == 3000.0

    def test_crypto_st_and_lt_mixed(self):
        """Mixed short-term and long-term crypto transactions."""
        income = Income(
            virtual_currency_transactions=[
                VirtualCurrencyTransaction(
                    transaction_type=VirtualCurrencyTransactionType.SALE,
                    asset_name="ETH",
                    quantity=2.0,
                    cost_basis=2000.0,
                    proceeds=5000.0,  # $3000 ST gain
                    is_long_term=False,
                ),
                VirtualCurrencyTransaction(
                    transaction_type=VirtualCurrencyTransactionType.SALE,
                    asset_name="BTC",
                    quantity=0.5,
                    cost_basis=10000.0,
                    proceeds=3000.0,  # $7000 LT loss
                    is_long_term=True,
                ),
            ]
        )
        result = income.calculate_net_capital_gain_loss("single")
        _, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        assert net_st == 3000.0
        assert net_lt == -7000.0
        # Overall: -4000
        assert loss_ded == 3000.0
        assert lt_cf == 1000.0  # Only LT is a loss


class TestEngineIntegration:
    """Tests for full engine integration."""

    def test_engine_populates_breakdown(self):
        """Engine calculation populates capital loss breakdown fields."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                short_term_capital_gains=0.0,
                long_term_capital_gains=0.0,
                long_term_loss_carryforward=10000.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        assert breakdown.capital_loss_deduction == 3000.0
        assert breakdown.new_lt_loss_carryforward == 7000.0
        assert breakdown.new_st_loss_carryforward == 0.0
        assert breakdown.net_long_term_gain_loss == -10000.0

    def test_engine_with_gains_no_carryforward(self):
        """Engine with net gains produces no carryforward."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                short_term_capital_gains=5000.0,
                long_term_capital_gains=10000.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        assert breakdown.capital_loss_deduction == 0.0
        assert breakdown.new_st_loss_carryforward == 0.0
        assert breakdown.new_lt_loss_carryforward == 0.0
        assert breakdown.net_short_term_gain_loss == 5000.0
        assert breakdown.net_long_term_gain_loss == 10000.0

    def test_engine_mfs_limit(self):
        """Engine applies MFS $1,500 limit."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.MARRIED_SEPARATE,
            ),
            income=Income(
                short_term_loss_carryforward=5000.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        assert breakdown.capital_loss_deduction == 1500.0
        assert breakdown.new_st_loss_carryforward == 3500.0


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_everything(self):
        """No capital activity returns zeros."""
        income = Income()
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        assert net_gain == 0.0
        assert loss_ded == 0.0
        assert st_cf == 0.0
        assert lt_cf == 0.0
        assert net_st == 0.0
        assert net_lt == 0.0

    def test_breakeven_no_gain_no_loss(self):
        """Gains exactly equal losses."""
        income = Income(
            short_term_capital_gains=5000.0,
            long_term_loss_carryforward=5000.0,
        )
        result = income.calculate_net_capital_gain_loss("single")
        net_gain, loss_ded, st_cf, lt_cf, net_st, net_lt = result

        assert net_gain == 0.0
        assert loss_ded == 0.0
        assert st_cf == 0.0
        assert lt_cf == 0.0

    def test_all_filing_statuses_use_3000_except_mfs(self):
        """All filing statuses except MFS use $3,000 limit."""
        income = Income(long_term_loss_carryforward=5000.0)

        for status in ["single", "married_joint", "head_of_household", "qualifying_widow"]:
            result = income.calculate_net_capital_gain_loss(status)
            _, loss_ded, _, lt_cf, _, _ = result
            assert loss_ded == 3000.0, f"Failed for {status}"
            assert lt_cf == 2000.0, f"Failed for {status}"
