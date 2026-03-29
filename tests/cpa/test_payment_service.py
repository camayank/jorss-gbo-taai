# tests/cpa/test_payment_service.py
import os
import sys
import sqlite3
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cpa_panel.payments.payment_service import PaymentService
from cpa_panel.payments.payment_models import Invoice, Payment, PaymentLink


@pytest.fixture
def svc(tmp_path):
    db = tmp_path / "test.db"
    with patch.dict(os.environ, {"DATABASE_PATH": str(db)}):
        return PaymentService()


def _row_count(db_path: Path, table: str) -> int:
    with sqlite3.connect(str(db_path)) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_persist_invoice_writes_row(svc, tmp_path):
    """_persist_invoice must store a row using invoice.id, not invoice.invoice_id."""
    inv = Invoice(firm_id=uuid.uuid4(), cpa_id=uuid.uuid4())
    inv.add_line_item("Tax prep", 500.0)
    svc._persist_invoice(inv)
    assert _row_count(tmp_path / "test.db", "pay_invoices") == 1


def test_persist_payment_writes_row(svc, tmp_path):
    """_persist_payment must store a row using payment.id, not payment.payment_id."""
    pay = Payment(firm_id=uuid.uuid4(), cpa_id=uuid.uuid4(), amount=150.0)
    svc._persist_payment(pay)
    assert _row_count(tmp_path / "test.db", "pay_payments") == 1


def test_persist_link_writes_row_with_link_code(svc, tmp_path):
    """_persist_link must store a row using link.id and link.link_code."""
    link = PaymentLink(firm_id=uuid.uuid4(), cpa_id=uuid.uuid4(), name="Q1 Retainer")
    svc._persist_link(link)
    db = tmp_path / "test.db"
    with sqlite3.connect(str(db)) as conn:
        row = conn.execute("SELECT link_id, code FROM pay_links LIMIT 1").fetchone()
    assert row is not None
    assert row[0] == str(link.id)           # link.id not link.link_id
    assert row[1] == link.link_code         # link.link_code not getattr(link,'code','')


def test_load_from_db_restores_invoices(tmp_path):
    """After restart, a new PaymentService instance loads persisted invoices."""
    db = tmp_path / "test.db"
    firm = uuid.uuid4()
    cpa = uuid.uuid4()

    # First instance — create and persist
    with patch.dict(os.environ, {"DATABASE_PATH": str(db)}):
        svc1 = PaymentService()
        inv = svc1.create_invoice(
            firm_id=firm, cpa_id=cpa, cpa_name="Alice CPA", firm_name="Acme",
            client_name="Bob", client_email="bob@example.com",
            line_items=[{"description": "Tax prep", "amount": 800.0}],
        )
        inv_id = inv.id

    # Second instance — simulates restart
    with patch.dict(os.environ, {"DATABASE_PATH": str(db)}):
        svc2 = PaymentService()
        loaded = svc2.get_invoice(inv_id)

    assert loaded is not None
    assert loaded.id == inv_id
    assert loaded.client_name == "Bob"
    assert loaded.total_amount == 800.0


def test_load_from_db_restores_payments(tmp_path):
    """After restart, a new PaymentService loads persisted payments."""
    db = tmp_path / "test.db"
    firm = uuid.uuid4()
    cpa = uuid.uuid4()

    with patch.dict(os.environ, {"DATABASE_PATH": str(db)}):
        svc1 = PaymentService()
        inv = svc1.create_invoice(
            firm_id=firm, cpa_id=cpa, cpa_name="Alice CPA", firm_name="Acme",
            client_name="Bob", client_email="bob@example.com",
            line_items=[{"description": "Tax prep", "amount": 500.0}],
        )
        _invoice, payment = svc1.record_payment(inv.id, 500.0)
        pay_id = payment.id

    with patch.dict(os.environ, {"DATABASE_PATH": str(db)}):
        svc2 = PaymentService()
        loaded = svc2._payments.get(pay_id)

    assert loaded is not None
    assert loaded.amount == 500.0


def test_load_from_db_restores_payment_links(tmp_path):
    """After restart, a new PaymentService loads persisted payment links."""
    db = tmp_path / "test.db"
    firm = uuid.uuid4()
    cpa = uuid.uuid4()

    with patch.dict(os.environ, {"DATABASE_PATH": str(db)}):
        svc1 = PaymentService()
        link = svc1.create_payment_link(
            firm_id=firm, cpa_id=cpa, name="Q1 Retainer", amount=1200.0
        )
        code = link.link_code

    with patch.dict(os.environ, {"DATABASE_PATH": str(db)}):
        svc2 = PaymentService()
        loaded = svc2.get_payment_link_by_code(code)

    assert loaded is not None
    assert loaded.name == "Q1 Retainer"
    assert loaded.amount == 1200.0


def test_load_from_db_roundtrip_apostrophe_in_description(tmp_path):
    """Line item descriptions with apostrophes must survive a persist/load cycle."""
    db = tmp_path / "test.db"
    firm = uuid.uuid4()
    cpa = uuid.uuid4()

    with patch.dict(os.environ, {"DATABASE_PATH": str(db)}):
        svc1 = PaymentService()
        inv = svc1.create_invoice(
            firm_id=firm, cpa_id=cpa, cpa_name="O'Brien CPA", firm_name="O'Brien & Co",
            client_name="Smith's Bakery", client_email="smith@example.com",
            line_items=[{"description": "O'Brien quarterly prep fee", "amount": 750.0}],
        )
        inv_id = inv.id

    with patch.dict(os.environ, {"DATABASE_PATH": str(db)}):
        svc2 = PaymentService()
        loaded = svc2.get_invoice(inv_id)

    assert loaded is not None
    assert loaded.line_items[0].description == "O'Brien quarterly prep fee"
    assert loaded.total_amount == 750.0
