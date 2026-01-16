"""
Tests for Phase 1 Domain Models.

Tests the following domain building blocks:
- Value Objects (PriorYearCarryovers, ScenarioModification, etc.)
- Aggregates (Scenario, AdvisoryPlan, ClientProfile)
- Domain Events
- Event Bus
"""

import pytest
from uuid import uuid4, UUID
from datetime import datetime
import tempfile
from pathlib import Path

# Import domain models
from domain.value_objects import (
    PriorYearCarryovers,
    PriorYearSummary,
    ScenarioModification,
    ScenarioResult,
    RecommendationAction,
)
from domain.aggregates import (
    Scenario,
    ScenarioType,
    ScenarioStatus,
    AdvisoryPlan,
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationStatus,
    ClientProfile,
    ClientPreferences,
    RiskTolerance,
)
from domain.events import (
    DomainEvent,
    EventType,
    TaxReturnCreated,
    TaxReturnCalculated,
    ScenarioCreated,
    RecommendationGenerated,
    create_event,
)
from domain.event_bus import (
    EventBus,
    SQLiteEventStore,
    AuditEventHandler,
    LoggingEventHandler,
)


# =============================================================================
# VALUE OBJECT TESTS
# =============================================================================

class TestPriorYearCarryovers:
    """Tests for PriorYearCarryovers value object."""

    def test_default_values(self):
        """Test default carryover values are zero."""
        carryovers = PriorYearCarryovers()

        assert carryovers.short_term_capital_loss_carryover == 0.0
        assert carryovers.long_term_capital_loss_carryover == 0.0
        assert carryovers.nol_carryover == 0.0
        assert carryovers.amt_credit_carryover == 0.0

    def test_capital_loss_carryover_total(self):
        """Test total capital loss carryover calculation."""
        carryovers = PriorYearCarryovers(
            short_term_capital_loss_carryover=5000.0,
            long_term_capital_loss_carryover=10000.0
        )

        assert carryovers.get_total_capital_loss_carryover() == 15000.0

    def test_charitable_carryover_total(self):
        """Test total charitable carryover calculation."""
        carryovers = PriorYearCarryovers(
            charitable_cash_60pct_carryover=1000.0,
            charitable_cash_50pct_carryover=500.0,
            charitable_property_30pct_carryover=2000.0,
            charitable_property_20pct_carryover=200.0
        )

        assert carryovers.get_total_charitable_carryover() == 3700.0

    def test_nol_carryover_total(self):
        """Test total NOL carryover calculation."""
        carryovers = PriorYearCarryovers(
            nol_carryover_post_2017=50000.0,
            nol_carryover_pre_2018=10000.0
        )

        assert carryovers.get_total_nol_carryover() == 60000.0

    def test_has_carryovers(self):
        """Test carryover detection."""
        empty = PriorYearCarryovers()
        assert not empty.has_carryovers()

        with_carryover = PriorYearCarryovers(amt_credit_carryover=1000.0)
        assert with_carryover.has_carryovers()

    def test_amt_credit_by_year(self):
        """Test AMT credit breakdown by year."""
        carryovers = PriorYearCarryovers(
            amt_credit_carryover=5000.0,
            amt_credit_by_year={2022: 2000.0, 2023: 3000.0}
        )

        assert carryovers.amt_credit_by_year[2022] == 2000.0
        assert carryovers.amt_credit_by_year[2023] == 3000.0


class TestScenarioModification:
    """Tests for ScenarioModification value object."""

    def test_create_modification(self):
        """Test creating a modification."""
        mod = ScenarioModification(
            field_path="income.retirement_contributions",
            original_value=0,
            new_value=23000,
            description="Max out 401k"
        )

        assert mod.field_path == "income.retirement_contributions"
        assert mod.original_value == 0
        assert mod.new_value == 23000

    def test_to_dict(self):
        """Test serialization to dict."""
        mod = ScenarioModification(
            field_path="deductions.charitable",
            original_value=1000,
            new_value=5000
        )

        d = mod.to_dict()
        assert d["field_path"] == "deductions.charitable"
        assert d["original_value"] == 1000
        assert d["new_value"] == 5000


class TestScenarioResult:
    """Tests for ScenarioResult value object."""

    def test_create_result(self):
        """Test creating a scenario result."""
        result = ScenarioResult(
            total_tax=15000.0,
            federal_tax=12000.0,
            state_tax=3000.0,
            effective_rate=0.18,
            base_tax=17000.0,
            savings=2000.0,
            savings_percent=11.76,
            taxable_income=80000.0
        )

        assert result.total_tax == 15000.0
        assert result.savings == 2000.0
        assert result.savings_percent == 11.76


# =============================================================================
# AGGREGATE TESTS
# =============================================================================

class TestScenarioAggregate:
    """Tests for Scenario aggregate."""

    def test_create_scenario(self):
        """Test creating a scenario."""
        return_id = uuid4()
        scenario = Scenario(
            return_id=return_id,
            name="Max 401k Contribution",
            scenario_type=ScenarioType.RETIREMENT
        )

        assert scenario.return_id == return_id
        assert scenario.name == "Max 401k Contribution"
        assert scenario.scenario_type == ScenarioType.RETIREMENT
        assert scenario.status == ScenarioStatus.DRAFT

    def test_add_modification(self):
        """Test adding modifications to a scenario."""
        scenario = Scenario(
            return_id=uuid4(),
            name="Test Scenario"
        )

        mod = ScenarioModification(
            field_path="income.retirement",
            original_value=0,
            new_value=23000
        )
        scenario.add_modification(mod)

        assert len(scenario.modifications) == 1
        assert scenario.modifications[0].field_path == "income.retirement"

    def test_add_modification_updates_existing(self):
        """Test that adding a modification for the same path updates it."""
        scenario = Scenario(
            return_id=uuid4(),
            name="Test Scenario"
        )

        mod1 = ScenarioModification(
            field_path="income.retirement",
            original_value=0,
            new_value=10000
        )
        mod2 = ScenarioModification(
            field_path="income.retirement",
            original_value=0,
            new_value=23000
        )

        scenario.add_modification(mod1)
        scenario.add_modification(mod2)

        assert len(scenario.modifications) == 1
        assert scenario.modifications[0].new_value == 23000

    def test_remove_modification(self):
        """Test removing a modification."""
        scenario = Scenario(
            return_id=uuid4(),
            name="Test Scenario"
        )

        mod = ScenarioModification(
            field_path="income.retirement",
            original_value=0,
            new_value=23000
        )
        scenario.add_modification(mod)
        result = scenario.remove_modification("income.retirement")

        assert result is True
        assert len(scenario.modifications) == 0

    def test_set_result(self):
        """Test setting scenario result."""
        scenario = Scenario(
            return_id=uuid4(),
            name="Test Scenario"
        )

        result = ScenarioResult(
            total_tax=15000.0,
            federal_tax=12000.0,
            effective_rate=0.18,
            base_tax=17000.0,
            savings=2000.0,
            savings_percent=11.76,
            taxable_income=80000.0
        )
        scenario.set_result(result)

        assert scenario.result == result
        assert scenario.status == ScenarioStatus.CALCULATED
        assert scenario.calculated_at is not None

    def test_mark_as_recommended(self):
        """Test marking a scenario as recommended."""
        scenario = Scenario(
            return_id=uuid4(),
            name="Optimal Filing Status"
        )

        scenario.mark_as_recommended("Provides maximum tax savings")

        assert scenario.is_recommended is True
        assert scenario.recommendation_reason == "Provides maximum tax savings"

    def test_to_comparison_dict(self):
        """Test conversion to comparison dictionary."""
        scenario = Scenario(
            return_id=uuid4(),
            name="Head of Household",
            scenario_type=ScenarioType.FILING_STATUS
        )

        result = ScenarioResult(
            total_tax=15000.0,
            federal_tax=12000.0,
            effective_rate=0.18,
            base_tax=17000.0,
            savings=2000.0,
            savings_percent=11.76,
            taxable_income=80000.0
        )
        scenario.set_result(result)

        d = scenario.to_comparison_dict()
        assert d["name"] == "Head of Household"
        assert d["type"] == "filing_status"
        assert d["total_tax"] == 15000.0
        assert d["savings"] == 2000.0


class TestAdvisoryPlanAggregate:
    """Tests for AdvisoryPlan aggregate."""

    def test_create_advisory_plan(self):
        """Test creating an advisory plan."""
        client_id = uuid4()
        return_id = uuid4()

        plan = AdvisoryPlan(
            client_id=client_id,
            return_id=return_id,
            tax_year=2025
        )

        assert plan.client_id == client_id
        assert plan.return_id == return_id
        assert plan.tax_year == 2025
        assert len(plan.recommendations) == 0

    def test_add_recommendation(self):
        """Test adding a recommendation."""
        plan = AdvisoryPlan(
            client_id=uuid4(),
            return_id=uuid4(),
            tax_year=2025
        )

        rec = Recommendation(
            category=RecommendationCategory.RETIREMENT,
            priority=RecommendationPriority.IMMEDIATE,
            title="Max out 401k",
            summary="Contribute maximum to 401k before Dec 31",
            estimated_savings=5400.0
        )
        plan.add_recommendation(rec)

        assert len(plan.recommendations) == 1
        assert plan.total_potential_savings == 5400.0

    def test_recalculate_totals(self):
        """Test that totals are recalculated when recommendations change."""
        plan = AdvisoryPlan(
            client_id=uuid4(),
            return_id=uuid4(),
            tax_year=2025
        )

        rec1 = Recommendation(
            category=RecommendationCategory.RETIREMENT,
            priority=RecommendationPriority.IMMEDIATE,
            title="Max 401k",
            summary="Test",
            estimated_savings=5000.0
        )
        rec2 = Recommendation(
            category=RecommendationCategory.HEALTHCARE,
            priority=RecommendationPriority.CURRENT_YEAR,
            title="Open HSA",
            summary="Test",
            estimated_savings=1100.0
        )

        plan.add_recommendation(rec1)
        plan.add_recommendation(rec2)

        assert plan.total_potential_savings == 6100.0

    def test_get_by_priority(self):
        """Test filtering recommendations by priority."""
        plan = AdvisoryPlan(
            client_id=uuid4(),
            return_id=uuid4(),
            tax_year=2025
        )

        rec1 = Recommendation(
            category=RecommendationCategory.RETIREMENT,
            priority=RecommendationPriority.IMMEDIATE,
            title="Immediate Action",
            summary="Test"
        )
        rec2 = Recommendation(
            category=RecommendationCategory.ESTATE,
            priority=RecommendationPriority.LONG_TERM,
            title="Long Term Planning",
            summary="Test"
        )

        plan.add_recommendation(rec1)
        plan.add_recommendation(rec2)

        immediate = plan.get_by_priority(RecommendationPriority.IMMEDIATE)
        assert len(immediate) == 1
        assert immediate[0].title == "Immediate Action"

    def test_finalize_plan(self):
        """Test finalizing a plan."""
        plan = AdvisoryPlan(
            client_id=uuid4(),
            return_id=uuid4(),
            tax_year=2025
        )

        plan.finalize("John Smith, CPA")

        assert plan.is_finalized is True
        assert plan.finalized_by == "John Smith, CPA"
        assert plan.finalized_at is not None


class TestClientProfileAggregate:
    """Tests for ClientProfile aggregate."""

    def test_create_client(self):
        """Test creating a client profile."""
        client = ClientProfile(
            first_name="John",
            last_name="Doe",
            email="john.doe@email.com"
        )

        assert client.first_name == "John"
        assert client.last_name == "Doe"
        assert client.full_name == "John Doe"
        assert client.is_active is True

    def test_add_tax_return(self):
        """Test adding a tax return reference."""
        client = ClientProfile(
            first_name="Jane",
            last_name="Smith"
        )

        return_id = uuid4()
        client.add_tax_return(return_id, 2025)

        assert return_id in client.tax_return_ids
        assert client.tax_return_years[2025] == return_id

    def test_get_prior_year_return(self):
        """Test getting prior year return."""
        client = ClientProfile(
            first_name="Bob",
            last_name="Jones"
        )

        return_2024 = uuid4()
        return_2025 = uuid4()
        client.add_tax_return(return_2024, 2024)
        client.add_tax_return(return_2025, 2025)

        prior = client.get_prior_year_return(2025)
        assert prior == return_2024

    def test_update_carryovers(self):
        """Test updating carryovers."""
        client = ClientProfile(
            first_name="Alice",
            last_name="Brown"
        )

        carryovers = PriorYearCarryovers(
            amt_credit_carryover=5000.0,
            short_term_capital_loss_carryover=3000.0
        )
        client.update_carryovers(carryovers)

        assert client.prior_year_carryovers is not None
        assert client.prior_year_carryovers.amt_credit_carryover == 5000.0

    def test_to_summary_dict(self):
        """Test summary dictionary generation."""
        client = ClientProfile(
            first_name="Test",
            last_name="User",
            external_id="CLIENT-001"
        )
        client.add_tax_return(uuid4(), 2024)
        client.add_tax_return(uuid4(), 2025)

        summary = client.to_summary_dict()
        assert summary["name"] == "Test User"
        assert summary["external_id"] == "CLIENT-001"
        assert 2024 in summary["tax_years_on_file"]
        assert 2025 in summary["tax_years_on_file"]


# =============================================================================
# DOMAIN EVENT TESTS
# =============================================================================

class TestDomainEvents:
    """Tests for domain events."""

    def test_tax_return_created_event(self):
        """Test TaxReturnCreated event."""
        return_id = uuid4()
        event = TaxReturnCreated(
            return_id=return_id,
            tax_year=2025,
            filing_status="married_joint",
            aggregate_id=return_id
        )

        assert event.event_type == EventType.TAX_RETURN_CREATED
        assert event.return_id == return_id
        assert event.tax_year == 2025

    def test_tax_return_calculated_event(self):
        """Test TaxReturnCalculated event."""
        return_id = uuid4()
        event = TaxReturnCalculated(
            return_id=return_id,
            tax_year=2025,
            gross_income=150000.0,
            adjusted_gross_income=130000.0,
            taxable_income=100000.0,
            total_tax=18000.0,
            effective_rate=0.12,
            refund_or_owed=-2000.0,
            computation_time_ms=150,
            forms_calculated=["Form 1040", "Schedule A"],
            aggregate_id=return_id
        )

        assert event.total_tax == 18000.0
        assert event.effective_rate == 0.12

    def test_scenario_created_event(self):
        """Test ScenarioCreated event."""
        scenario_id = uuid4()
        return_id = uuid4()

        event = ScenarioCreated(
            scenario_id=scenario_id,
            return_id=return_id,
            name="Filing Status Comparison",
            scenario_type="filing_status",
            aggregate_id=scenario_id
        )

        assert event.event_type == EventType.SCENARIO_CREATED
        assert event.scenario_id == scenario_id

    def test_create_event_factory(self):
        """Test event factory function."""
        return_id = uuid4()
        event = create_event(
            EventType.TAX_RETURN_CREATED,
            return_id=return_id,
            tax_year=2025,
            filing_status="single",
            aggregate_id=return_id
        )

        assert isinstance(event, TaxReturnCreated)
        assert event.return_id == return_id


# =============================================================================
# EVENT BUS TESTS
# =============================================================================

class TestEventBus:
    """Tests for EventBus."""

    def test_subscribe_and_publish(self):
        """Test subscribing and publishing events."""
        bus = EventBus()
        received_events = []

        def handler(event: DomainEvent):
            received_events.append(event)

        bus.subscribe(TaxReturnCreated, handler)

        event = TaxReturnCreated(
            return_id=uuid4(),
            tax_year=2025,
            filing_status="single",
            aggregate_id=uuid4()
        )
        bus.publish(event)

        assert len(received_events) == 1
        assert received_events[0] == event

    def test_global_handler(self):
        """Test global event handler."""
        bus = EventBus()
        received_events = []

        def handler(event: DomainEvent):
            received_events.append(event)

        bus.subscribe_all(handler)

        event1 = TaxReturnCreated(
            return_id=uuid4(),
            tax_year=2025,
            filing_status="single",
            aggregate_id=uuid4()
        )
        event2 = ScenarioCreated(
            scenario_id=uuid4(),
            return_id=uuid4(),
            name="Test",
            scenario_type="what_if",
            aggregate_id=uuid4()
        )

        bus.publish(event1)
        bus.publish(event2)

        assert len(received_events) == 2

    def test_unsubscribe(self):
        """Test unsubscribing from events."""
        bus = EventBus()
        received_events = []

        def handler(event: DomainEvent):
            received_events.append(event)

        bus.subscribe(TaxReturnCreated, handler)
        bus.unsubscribe(TaxReturnCreated, handler)

        event = TaxReturnCreated(
            return_id=uuid4(),
            tax_year=2025,
            filing_status="single",
            aggregate_id=uuid4()
        )
        bus.publish(event)

        assert len(received_events) == 0


# =============================================================================
# EVENT STORE TESTS
# =============================================================================

class TestSQLiteEventStore:
    """Tests for SQLiteEventStore."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield Path(f.name)

    @pytest.mark.asyncio
    async def test_append_and_get_events(self, temp_db):
        """Test appending and retrieving events."""
        store = SQLiteEventStore(temp_db)
        return_id = uuid4()
        stream_id = f"tax_return:{return_id}"

        event = TaxReturnCreated(
            return_id=return_id,
            tax_year=2025,
            filing_status="single",
            aggregate_id=return_id,
            aggregate_type="tax_return"
        )

        await store.append(stream_id, event)
        events = await store.get_events(stream_id)

        assert len(events) == 1
        assert events[0].event_type == EventType.TAX_RETURN_CREATED

    @pytest.mark.asyncio
    async def test_stream_versioning(self, temp_db):
        """Test event stream versioning."""
        store = SQLiteEventStore(temp_db)
        return_id = uuid4()
        stream_id = f"tax_return:{return_id}"

        event1 = TaxReturnCreated(
            return_id=return_id,
            tax_year=2025,
            filing_status="single",
            aggregate_id=return_id,
            aggregate_type="tax_return"
        )
        event2 = TaxReturnCalculated(
            return_id=return_id,
            tax_year=2025,
            gross_income=100000.0,
            adjusted_gross_income=90000.0,
            taxable_income=70000.0,
            total_tax=12000.0,
            effective_rate=0.12,
            refund_or_owed=500.0,
            computation_time_ms=100,
            aggregate_id=return_id,
            aggregate_type="tax_return"
        )

        await store.append(stream_id, event1)
        await store.append(stream_id, event2)

        version = await store.get_stream_version(stream_id)
        assert version == 2

    @pytest.mark.asyncio
    async def test_get_events_by_type(self, temp_db):
        """Test getting events by type."""
        store = SQLiteEventStore(temp_db)

        # Create events
        for _ in range(3):
            return_id = uuid4()
            event = TaxReturnCreated(
                return_id=return_id,
                tax_year=2025,
                filing_status="single",
                aggregate_id=return_id,
                aggregate_type="tax_return"
            )
            await store.append(f"tax_return:{return_id}", event)

        events = await store.get_events_by_type("tax_return.created")
        assert len(events) == 3


# =============================================================================
# RECOMMENDATION TESTS
# =============================================================================

class TestRecommendation:
    """Tests for Recommendation entity."""

    def test_create_recommendation(self):
        """Test creating a recommendation."""
        rec = Recommendation(
            category=RecommendationCategory.RETIREMENT,
            priority=RecommendationPriority.IMMEDIATE,
            title="Maximize 401k Contributions",
            summary="Contribute the maximum $23,500 to your 401k before Dec 31",
            estimated_savings=5400.0,
            action_steps=[
                RecommendationAction(
                    step_number=1,
                    action="Contact HR to increase contribution",
                    deadline="December 1"
                )
            ]
        )

        assert rec.category == RecommendationCategory.RETIREMENT
        assert rec.status == RecommendationStatus.PROPOSED
        assert len(rec.action_steps) == 1

    def test_update_status(self):
        """Test updating recommendation status."""
        rec = Recommendation(
            category=RecommendationCategory.DEDUCTION,
            priority=RecommendationPriority.CURRENT_YEAR,
            title="Charitable Bunching",
            summary="Bundle charitable contributions"
        )

        rec.update_status(RecommendationStatus.ACCEPTED, "Client")

        assert rec.status == RecommendationStatus.ACCEPTED
        assert rec.status_changed_by == "Client"
        assert rec.status_changed_at is not None

    def test_record_outcome(self):
        """Test recording recommendation outcome."""
        rec = Recommendation(
            category=RecommendationCategory.RETIREMENT,
            priority=RecommendationPriority.IMMEDIATE,
            title="Test Recommendation",
            summary="Test",
            estimated_savings=5000.0
        )

        rec.record_outcome(4800.0, "Slightly less than expected due to income change")

        assert rec.actual_savings == 4800.0
        assert rec.status == RecommendationStatus.IMPLEMENTED
        assert rec.outcome_notes is not None

    def test_savings_accuracy(self):
        """Test savings accuracy calculation."""
        rec = Recommendation(
            category=RecommendationCategory.RETIREMENT,
            priority=RecommendationPriority.IMMEDIATE,
            title="Test",
            summary="Test",
            estimated_savings=5000.0
        )
        rec.actual_savings = 4500.0

        accuracy = rec.get_savings_accuracy()
        assert accuracy == 0.9  # 4500/5000
