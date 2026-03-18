"""Tests for AIMetricsService._check_budget_alerts() budget threshold logic."""

import pytest
from datetime import datetime
from typing import Optional

from services.ai.metrics_service import AIMetricsService, UsageRecord
from config.ai_providers import AIProvider, ModelCapability


def _make_record(cost: float, timestamp: Optional[datetime] = None) -> UsageRecord:
    """Helper to create a UsageRecord with the given cost."""
    return UsageRecord(
        timestamp=timestamp or datetime.now(),
        provider=AIProvider.OPENAI,
        model="gpt-4o",
        capability=ModelCapability.STANDARD,
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        latency_ms=200,
        cost=cost,
        success=True,
    )


class TestCheckBudgetAlerts:
    """Tests for _check_budget_alerts() method."""

    def test_no_alert_when_spend_below_80_percent(self, monkeypatch):
        """No alert emitted when spend is below the 80% warning threshold."""
        monkeypatch.setenv("AI_MONTHLY_BUDGET_USD", "100")
        svc = AIMetricsService(persist_path=None)
        svc._records.append(_make_record(cost=79.0))

        svc._check_budget_alerts()

        assert len(svc._budget_alerts) == 0

    def test_warning_alert_at_80_percent(self, monkeypatch):
        """Warning alert fires when spend reaches 80% of budget."""
        monkeypatch.setenv("AI_MONTHLY_BUDGET_USD", "100")
        svc = AIMetricsService(persist_path=None)
        svc._records.append(_make_record(cost=80.0))

        svc._check_budget_alerts()

        assert len(svc._budget_alerts) == 1
        assert svc._budget_alerts[0]["level"] == "warning"

    def test_critical_alert_at_95_percent(self, monkeypatch):
        """Critical alert fires when spend reaches 95% of budget."""
        monkeypatch.setenv("AI_MONTHLY_BUDGET_USD", "100")
        svc = AIMetricsService(persist_path=None)
        svc._records.append(_make_record(cost=95.0))

        svc._check_budget_alerts()

        assert len(svc._budget_alerts) == 1
        assert svc._budget_alerts[0]["level"] == "critical"

    def test_deduplication_same_level_not_repeated(self, monkeypatch):
        """Same alert level is not repeated within the same month."""
        monkeypatch.setenv("AI_MONTHLY_BUDGET_USD", "100")
        svc = AIMetricsService(persist_path=None)
        svc._records.append(_make_record(cost=85.0))

        svc._check_budget_alerts()
        svc._check_budget_alerts()  # call again -- should not duplicate

        warning_alerts = [a for a in svc._budget_alerts if a["level"] == "warning"]
        assert len(warning_alerts) == 1

    def test_both_warning_and_critical_can_fire_same_month(self, monkeypatch):
        """Warning and critical can both fire within the same month."""
        monkeypatch.setenv("AI_MONTHLY_BUDGET_USD", "100")
        svc = AIMetricsService(persist_path=None)

        # First trigger warning
        svc._records.append(_make_record(cost=82.0))
        svc._check_budget_alerts()
        assert len(svc._budget_alerts) == 1
        assert svc._budget_alerts[0]["level"] == "warning"

        # Add more spend to push past critical
        svc._records.append(_make_record(cost=14.0))  # total = 96
        svc._check_budget_alerts()
        assert len(svc._budget_alerts) == 2
        levels = {a["level"] for a in svc._budget_alerts}
        assert levels == {"warning", "critical"}

    def test_budget_read_from_env_var(self, monkeypatch):
        """Budget limit is read from AI_MONTHLY_BUDGET_USD env var."""
        monkeypatch.setenv("AI_MONTHLY_BUDGET_USD", "200")
        svc = AIMetricsService(persist_path=None)
        # 160 / 200 = 80% exactly -- should trigger warning
        svc._records.append(_make_record(cost=160.0))

        svc._check_budget_alerts()

        assert len(svc._budget_alerts) == 1
        assert svc._budget_alerts[0]["limit"] == 200.0

    def test_zero_budget_skips_check(self, monkeypatch):
        """When budget is zero, _check_budget_alerts returns without firing."""
        monkeypatch.setenv("AI_MONTHLY_BUDGET_USD", "0")
        svc = AIMetricsService(persist_path=None)
        svc._records.append(_make_record(cost=1000.0))

        svc._check_budget_alerts()

        assert len(svc._budget_alerts) == 0

    def test_alert_includes_correct_spend_limit_percentage(self, monkeypatch):
        """Alert dict contains accurate spend, limit, and usage_pct values."""
        monkeypatch.setenv("AI_MONTHLY_BUDGET_USD", "500")
        svc = AIMetricsService(persist_path=None)
        svc._records.append(_make_record(cost=475.0))  # 95%

        svc._check_budget_alerts()

        assert len(svc._budget_alerts) == 1
        alert = svc._budget_alerts[0]
        assert alert["spend"] == 475.0
        assert alert["limit"] == 500.0
        assert alert["usage_pct"] == 95.0
