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
