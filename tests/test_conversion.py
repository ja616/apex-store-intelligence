"""Tests for POS transaction attribution engine."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import List

import pytest

from apex.analytics.conversion import ConversionAttributionEngine
from apex.models.sessions import Session as SessionModel, ZoneVisit
from apex.models.transactions import Transaction

STORE_ID = "brigade-road-bangalore"
BASE_TIME = datetime(2026, 4, 10, 14, 0, 0)


def _make_session_with_billing(
    db,
    visitor_id: str,
    billing_exit_offset: int = 200,
    billing_dwell: float = 120.0,
    confidence: float = 0.85,
) -> SessionModel:
    """Create a session that includes a billing zone visit."""
    sid = str(uuid.uuid4())
    sess = SessionModel(
        session_id=sid,
        visitor_id=visitor_id,
        store_id=STORE_ID,
        entry_time=BASE_TIME,
        exit_time=BASE_TIME + timedelta(seconds=billing_exit_offset + 30),
        duration_seconds=billing_exit_offset + 30,
        converted=False,
        session_confidence=confidence,
        is_staff=False,
        reentry_count=0,
        zones_visited=["entry", "billing"],
    )
    zv = ZoneVisit(
        session_id=sid,
        camera_id="CAM4",
        zone_name="billing",
        entry_time=BASE_TIME + timedelta(seconds=billing_exit_offset - billing_dwell),
        exit_time=BASE_TIME + timedelta(seconds=billing_exit_offset),
        dwell_seconds=billing_dwell,
        confidence=confidence,
    )
    db.add(sess)
    db.add(zv)
    db.flush()
    sess.zone_visits = [zv]
    return sess


def _make_transaction(
    db,
    offset_seconds: int,
    txn_id: str | None = None,
) -> Transaction:
    txn = Transaction(
        transaction_id=txn_id or str(uuid.uuid4()),
        store_id=STORE_ID,
        timestamp=BASE_TIME + timedelta(seconds=offset_seconds),
        amount=500.0,
        nmv=400.0,
        qty=2,
        is_attributed=False,
    )
    db.add(txn)
    db.flush()
    return txn


@pytest.fixture
def engine():
    return ConversionAttributionEngine(
        billing_window_seconds=600,  # 10-min window
        billing_cameras=["CAM4", "CAM5"],
    )


class TestTransactionWithinWindow:
    """Transaction within billing window → converted=True, confidence > 0.8."""

    def test_attribution_within_window(self, db_session, engine):
        vid = str(uuid.uuid4())
        # Billing zone exit at T+200s
        _make_session_with_billing(db_session, vid, billing_exit_offset=200, confidence=0.9)
        # Transaction at T+250s (50s after exit — within 600s window)
        txn = _make_transaction(db_session, offset_seconds=250)
        db_session.commit()

        results = engine.attribute_sessions(STORE_ID, db_session)

        assert len(results) == 1
        r = results[0]
        assert r.attributed, "Transaction within window should be attributed"
        assert r.attribution_confidence > 0.8
        assert r.visitor_id == vid


class TestTransactionOutsideWindow:
    """Transaction outside billing window → not attributed."""

    def test_attribution_outside_window(self, db_session, engine):
        vid = str(uuid.uuid4())
        _make_session_with_billing(db_session, vid, billing_exit_offset=200)
        # Transaction at T+900s (700s after exit — outside 600s window)
        txn = _make_transaction(db_session, offset_seconds=900)
        db_session.commit()

        results = engine.attribute_sessions(STORE_ID, db_session)

        assert len(results) == 1
        r = results[0]
        assert not r.attributed, "Transaction outside window should NOT be attributed"


class TestMultipleVisitorsClosestWins:
    """Multiple visitors in billing zone → closest temporal match wins."""

    def test_closest_visitor_attributed(self, db_session, engine):
        vid_close = str(uuid.uuid4())
        vid_far = str(uuid.uuid4())

        # Close visitor: billing exit at T+290s
        _make_session_with_billing(db_session, vid_close, billing_exit_offset=290)
        # Far visitor: billing exit at T+100s
        _make_session_with_billing(db_session, vid_far, billing_exit_offset=100)

        # Transaction at T+300s (10s after close visitor exits)
        txn = _make_transaction(db_session, offset_seconds=300)
        db_session.commit()

        results = engine.attribute_sessions(STORE_ID, db_session)

        attributed = [r for r in results if r.attributed]
        assert len(attributed) == 1, "Exactly one attribution expected"
        assert attributed[0].visitor_id == vid_close, "Closest visitor should win"


class TestUnattributedTransaction:
    """No matching sessions → transaction not force-assigned."""

    def test_transaction_without_session_not_assigned(self, db_session, engine):
        # No sessions in DB
        txn = _make_transaction(db_session, offset_seconds=100)
        db_session.commit()

        results = engine.attribute_sessions(STORE_ID, db_session)

        assert len(results) == 1
        assert not results[0].attributed


class TestIdempotentLoading:
    """Loading same CSV twice should not duplicate transactions."""

    def test_duplicate_transaction_skipped(self, db_session, engine):
        import tempfile, csv, os

        # Create minimal CSV
        rows = [
            {
                "order_id": "104363838",
                "invoice_number": "ML0426KAP0001358",
                "order_date": "10-04-2026",
                "order_time": "16:55:36",
                "store_id": "ST1008",
                "customer_name": "Guest",
                "customer_number": "9346413680",
                "sku": "PPLBDD8904362534994NM2",
                "product_id": "402813",
                "product_name": "DERMDOC Body Wash 250ml",
                "brand_name": "DERMDOC",
                "dep_name": "bath-and-body",
                "sub_category": "Body Wash",
                "qty": "1",
                "total_amount": "274.36",
                "NMV": "274.36",
                "salesperson_id": "1178",
            }
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
            tmp_path = f.name

        try:
            count1 = engine.load_transactions(tmp_path, STORE_ID, db_session)
            count2 = engine.load_transactions(tmp_path, STORE_ID, db_session)
        finally:
            os.unlink(tmp_path)

        assert count1 == 1, "First load should insert 1 row"
        assert count2 == 0, "Second load should skip duplicate"
