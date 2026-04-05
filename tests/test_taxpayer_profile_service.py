"""
Tests for TaxpayerProfileService - prior year loading and session pre-fill.
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import (
    Base,
    TaxReturnRecord,
    CarryforwardLedgerRecord,
    FilingStatusFlag,
    CarryforwardType,
    ReturnStatus,
)
from admin_panel.models.firm import Firm
from services.taxpayer_profile_service import (
    TaxpayerProfileService,
    PriorYearContext,
    LifeEvent,
)


@pytest.fixture
def db_session_with_firm():
    """Create in-memory SQLite database with a test firm."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create a default firm for foreign key references
    firm = Firm(
        firm_id=uuid4(),
        name="Test Firm",
        ein="12-3456789",
    )
    session.add(firm)
    session.commit()

    yield session, firm.firm_id
    session.close()


@pytest.fixture
def db_session(db_session_with_firm):
    """Extract just the session from the tuple."""
    session, _ = db_session_with_firm
    return session


@pytest.fixture
def firm_id(db_session_with_firm):
    """Extract the firm_id from the tuple."""
    _, firm_id_val = db_session_with_firm
    return firm_id_val


@pytest.fixture
def service(db_session):
    """Create TaxpayerProfileService with test database."""
    return TaxpayerProfileService(db_session)


class TestLoadPriorYearContext:
    """Tests for load_prior_year_context method."""

    def test_load_prior_year_context_found(self, db_session, service, firm_id):
        """Test loading prior year context when return exists."""
        # Create prior year return
        taxpayer_ssn_hash = "test_ssn_hash_12345"
        return_id = uuid4()

        prior_return = TaxReturnRecord(
            return_id=return_id,
            tax_year=2023,
            taxpayer_ssn_hash=taxpayer_ssn_hash,
            filing_status=FilingStatusFlag.SINGLE,
            status=ReturnStatus.FILED,
            firm_id=firm_id,
            line_11_agi=Decimal("75000.00"),
            line_1_wages=Decimal("75000.00"),
            line_3a_qualified_dividends=Decimal("0.00"),
            line_7_capital_gain_loss=Decimal("0.00"),
        )
        db_session.add(prior_return)
        db_session.commit()

        # Load prior year context for 2024
        context = service.load_prior_year_context(taxpayer_ssn_hash, 2024)

        assert context is not None
        assert context.tax_year == 2023
        assert context.filing_status == FilingStatusFlag.SINGLE
        assert context.agi == Decimal("75000.00")
        assert context.key_line_items["line_1_wages"] == Decimal("75000.00")

    def test_load_prior_year_context_not_found(self, db_session, service):
        """Test loading prior year context when no return exists."""
        context = service.load_prior_year_context("nonexistent_ssn", 2024)
        assert context is None

    def test_load_prior_year_context_with_carryforwards(self, db_session, service, firm_id):
        """Test loading prior year context includes carryforwards."""
        taxpayer_ssn_hash = "test_ssn_hash_carryforward"
        return_id = uuid4()

        # Create prior year return
        prior_return = TaxReturnRecord(
            return_id=return_id,
            tax_year=2023,
            taxpayer_ssn_hash=taxpayer_ssn_hash,
            filing_status=FilingStatusFlag.MARRIED_FILING_JOINTLY,
            status=ReturnStatus.FILED,
            firm_id=firm_id,
            line_11_agi=Decimal("100000.00"),
        )
        db_session.add(prior_return)

        # Create carryforward records
        nol_carryforward = CarryforwardLedgerRecord(
            ledger_id=uuid4(),
            firm_id=firm_id,
            return_id=return_id,
            taxpayer_ssn_hash=taxpayer_ssn_hash,
            tax_year=2023,
            carryforward_type=CarryforwardType.NET_OPERATING_LOSS,
            source_year=2022,
            amount_available=Decimal("50000.00"),
            amount_used=Decimal("10000.00"),
            amount_remaining=Decimal("40000.00"),
            expires_after_year=2029,
        )
        db_session.add(nol_carryforward)
        db_session.commit()

        # Load prior year context
        context = service.load_prior_year_context(taxpayer_ssn_hash, 2024)

        assert context is not None
        assert len(context.carryforwards) == 1
        assert context.carryforwards[0].carryforward_type == CarryforwardType.NET_OPERATING_LOSS
        assert context.carryforwards[0].amount_available == Decimal("50000.00")

    def test_load_multiple_years_gets_most_recent(self, db_session, service, firm_id):
        """Test that load gets most recent prior year return when multiple exist."""
        taxpayer_ssn_hash = "test_ssn_multiple"

        # Create multiple prior year returns
        return_2022 = TaxReturnRecord(
            return_id=uuid4(),
            tax_year=2022,
            taxpayer_ssn_hash=taxpayer_ssn_hash,
            filing_status=FilingStatusFlag.SINGLE,
            status=ReturnStatus.FILED,
            firm_id=firm_id,
            line_11_agi=Decimal("50000.00"),
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        )
        return_2023 = TaxReturnRecord(
            return_id=uuid4(),
            tax_year=2023,
            taxpayer_ssn_hash=taxpayer_ssn_hash,
            filing_status=FilingStatusFlag.MARRIED_FILING_JOINTLY,
            status=ReturnStatus.FILED,
            firm_id=firm_id,
            line_11_agi=Decimal("100000.00"),
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

        db_session.add(return_2022)
        db_session.add(return_2023)
        db_session.commit()

        # Load prior year context for 2024 - should get 2023
        context = service.load_prior_year_context(taxpayer_ssn_hash, 2024)

        assert context is not None
        assert context.tax_year == 2023
        assert context.filing_status == FilingStatusFlag.MARRIED_FILING_JOINTLY
        assert context.agi == Decimal("100000.00")


class TestPreFillStableFields:
    """Tests for pre_fill_stable_fields method."""

    def test_prefill_with_prior_context(self, db_session, service):
        """Test pre-filling session with prior year context."""
        # Create prior year context
        context = PriorYearContext(
            return_id=uuid4(),
            tax_year=2023,
            filing_status=FilingStatusFlag.SINGLE,
            agi=Decimal("75000.00"),
            key_line_items={"line_1_wages": Decimal("75000.00")},
            carryforwards=[],
            life_events=[],
        )

        session = {}
        updated_session = service.pre_fill_stable_fields(session, context)

        assert updated_session["filing_status"] == FilingStatusFlag.SINGLE.value
        assert "prior_year_reference" in updated_session
        assert updated_session["prior_year_reference"]["tax_year"] == 2023
        assert updated_session["prior_year_reference"]["agi"] == "75000.00"

    def test_prefill_preserves_existing_filing_status(self, db_session, service):
        """Test that pre-fill respects already-set filing status."""
        context = PriorYearContext(
            return_id=uuid4(),
            tax_year=2023,
            filing_status=FilingStatusFlag.SINGLE,
            agi=Decimal("75000.00"),
            key_line_items={},
            carryforwards=[],
            life_events=[],
        )

        session = {"filing_status": FilingStatusFlag.MARRIED_FILING_JOINTLY.value}
        updated_session = service.pre_fill_stable_fields(session, context)

        # Should preserve existing value (setdefault doesn't overwrite)
        assert updated_session["filing_status"] == FilingStatusFlag.MARRIED_FILING_JOINTLY.value

    def test_prefill_includes_carryforwards(self, db_session, service):
        """Test that pre-fill includes carryforward records."""
        carryforward = CarryforwardLedgerRecord(
            ledger_id=uuid4(),
            taxpayer_ssn_hash="test",
            tax_year=2023,
            carryforward_type=CarryforwardType.CAPITAL_LOSS,
            amount_available=Decimal("5000.00"),
        )

        context = PriorYearContext(
            return_id=uuid4(),
            tax_year=2023,
            filing_status=FilingStatusFlag.SINGLE,
            agi=Decimal("75000.00"),
            key_line_items={},
            carryforwards=[carryforward],
            life_events=[],
        )

        session = {}
        updated_session = service.pre_fill_stable_fields(session, context)

        assert "carryforwards" in updated_session
        assert len(updated_session["carryforwards"]) == 1
        assert updated_session["carryforwards"][0]["type"] == CarryforwardType.CAPITAL_LOSS.value

    def test_prefill_with_none_context(self, service):
        """Test pre-fill with None context returns unchanged session."""
        session = {"existing_key": "value"}
        updated_session = service.pre_fill_stable_fields(session, None)

        assert updated_session == session


class TestIntegration:
    """Integration tests for full workflow."""

    def test_full_workflow_load_and_prefill(self, db_session, service, firm_id):
        """Test complete workflow: load prior year, then pre-fill session."""
        # Setup
        taxpayer_ssn_hash = "integration_test_ssn"

        # Create prior year return with real data
        prior_return = TaxReturnRecord(
            return_id=uuid4(),
            tax_year=2023,
            taxpayer_ssn_hash=taxpayer_ssn_hash,
            filing_status=FilingStatusFlag.MARRIED_FILING_JOINTLY,
            status=ReturnStatus.FILED,
            firm_id=firm_id,
            line_11_agi=Decimal("150000.00"),
            line_1_wages=Decimal("140000.00"),
            line_3a_qualified_dividends=Decimal("5000.00"),
            line_12c_total_deduction=Decimal("28000.00"),
        )
        db_session.add(prior_return)

        # Create carryforward
        capital_loss = CarryforwardLedgerRecord(
            ledger_id=uuid4(),
            firm_id=firm_id,
            return_id=prior_return.return_id,
            taxpayer_ssn_hash=taxpayer_ssn_hash,
            tax_year=2023,
            carryforward_type=CarryforwardType.CAPITAL_LOSS,
            amount_available=Decimal("3000.00"),
        )
        db_session.add(capital_loss)
        db_session.commit()

        # Step 1: Load prior year context
        context = service.load_prior_year_context(taxpayer_ssn_hash, 2024)
        assert context is not None

        # Step 2: Pre-fill session
        session = {}
        updated_session = service.pre_fill_stable_fields(session, context)

        # Verify stable fields are pre-filled
        assert updated_session["filing_status"] == FilingStatusFlag.MARRIED_FILING_JOINTLY.value

        # Verify reference data is available (not auto-filled, but available)
        assert updated_session["prior_year_reference"]["agi"] == "150000.00"
        assert updated_session["prior_year_reference"]["key_line_items"]["line_1_wages"] == "140000.00"

        # Verify carryforwards are included
        assert len(updated_session["carryforwards"]) == 1
        assert updated_session["carryforwards"][0]["type"] == CarryforwardType.CAPITAL_LOSS.value
