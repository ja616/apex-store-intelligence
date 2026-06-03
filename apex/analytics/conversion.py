"""POS Transaction Attribution Engine.

Algorithm:
  1. Load CSV → Transaction rows (idempotent by invoice_number).
  2. For each un-attributed transaction, find sessions where visitor was in
     billing zone (CAM4 / CAM5).
  3. Match on temporal proximity: billing zone exit within
     billing_temporal_window_seconds of transaction timestamp.
  4. If multiple sessions match, assign to closest temporal match.
  5. attribution_confidence = 0.9 × temporal_proximity_score × identity_confidence.

CSV columns (Brigade Bangalore):
  order_id, invoice_number, order_date, order_time, store_id,
  customer_name, customer_number, product_name, brand_name, dep_name,
  sub_category, qty, GMV, NMV, total_amount, ...
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    _PANDAS_AVAILABLE = True
except ImportError:
    _PANDAS_AVAILABLE = False
    logger.warning("pandas not available — CSV loading will use csv module")

import csv as _csv
import io

from sqlalchemy.orm import Session as DBSession

from apex.config import settings
from apex.models.events import Event, EventType
from apex.models.sessions import Session, ZoneVisit
from apex.models.transactions import Transaction


@dataclass
class AttributionResult:
    """Result of attributing one transaction to one session."""
    transaction_id: str
    session_id: Optional[str]
    visitor_id: Optional[str]
    attributed: bool
    attribution_confidence: float
    attribution_reason: str
    temporal_gap_seconds: float = 0.0
    billing_dwell_seconds: float = 0.0


class ConversionAttributionEngine:
    """Load POS transactions and attribute them to visitor sessions."""

    # ── CSV column names in the Brigade Bangalore dataset ────────────────────
    _COL_ORDER_ID = "order_id"
    _COL_INVOICE = "invoice_number"
    _COL_DATE = "order_date"
    _COL_TIME = "order_time"
    _COL_STORE = "store_id"
    _COL_CUSTOMER = "customer_name"
    _COL_PHONE = "customer_number"
    _COL_PRODUCT = "product_name"
    _COL_BRAND = "brand_name"
    _COL_DEPT = "dep_name"
    _COL_SUBCAT = "sub_category"
    _COL_QTY = "qty"
    _COL_AMOUNT = "total_amount"
    _COL_NMV = "NMV"
    _COL_SALESPERSON = "salesperson_id"

    def __init__(
        self,
        billing_window_seconds: int | None = None,
        billing_cameras: List[str] | None = None,
    ) -> None:
        self.billing_window_seconds = (
            billing_window_seconds or settings.billing_temporal_window_seconds
        )
        self.billing_cameras = set(
            billing_cameras or settings.billing_zone_cameras
        )

    # ── Loading ───────────────────────────────────────────────────────────────

    def load_transactions(
        self,
        csv_path: str,
        store_id: str,
        db: DBSession,
    ) -> int:
        """Load CSV transactions into DB.  Returns count of rows inserted."""
        rows = self._parse_csv(csv_path)
        if not rows:
            return 0

        inserted = 0
        for row in rows:
            txn_id = self._make_txn_id(row)
            existing = db.get(Transaction, txn_id)
            if existing is not None:
                continue   # idempotent

            ts = self._parse_timestamp(row)
            if ts is None:
                logger.warning("Skipping row with unparseable timestamp: %s", row)
                continue

            amount = self._safe_float(row.get(self._COL_AMOUNT, 0))
            nmv = self._safe_float(row.get(self._COL_NMV, amount))

            txn = Transaction(
                transaction_id=txn_id,
                store_id=store_id,
                timestamp=ts,
                amount=amount,
                nmv=nmv,
                qty=int(self._safe_float(row.get(self._COL_QTY, 1))),
                customer_name=str(row.get(self._COL_CUSTOMER, "")).strip() or None,
                customer_number=str(row.get(self._COL_PHONE, "")).strip() or None,
                product_name=str(row.get(self._COL_PRODUCT, "")).strip() or None,
                brand_name=str(row.get(self._COL_BRAND, "")).strip() or None,
                department=str(row.get(self._COL_DEPT, "")).strip() or None,
                sub_category=str(row.get(self._COL_SUBCAT, "")).strip() or None,
                order_id=str(row.get(self._COL_ORDER_ID, "")).strip() or None,
                salesperson_id=str(row.get(self._COL_SALESPERSON, "")).strip() or None,
                is_attributed=False,
                raw_data=dict(row),
            )
            db.add(txn)
            inserted += 1

        try:
            db.commit()
        except Exception as exc:
            logger.error("Transaction commit failed: %s", exc)
            db.rollback()
            return 0

        logger.info("Loaded %d transactions for store=%s", inserted, store_id)
        return inserted

    # ── Attribution ───────────────────────────────────────────────────────────

    def attribute_sessions(
        self,
        store_id: str,
        db: DBSession,
    ) -> List[AttributionResult]:
        """Attribute un-matched transactions to visitor sessions.

        Returns list of AttributionResult (one per transaction).
        """
        # Fetch un-attributed transactions
        transactions: List[Transaction] = (
            db.query(Transaction)
            .filter(
                Transaction.store_id == store_id,
                Transaction.is_attributed == False,  # noqa: E712
            )
            .order_by(Transaction.timestamp)
            .all()
        )

        if not transactions:
            return []

        # Fetch sessions with billing zone visits
        sessions_with_billing = self._get_billing_sessions(store_id, db)

        results: List[AttributionResult] = []

        for txn in transactions:
            result = self._attribute_one(txn, sessions_with_billing, db)
            results.append(result)

        try:
            db.commit()
        except Exception as exc:
            logger.error("Attribution commit failed: %s", exc)
            db.rollback()

        return results

    def _get_billing_sessions(
        self, store_id: str, db: DBSession
    ) -> List[Dict[str, Any]]:
        """Return sessions that have billing zone visits, with their exit times."""
        # Join Session → ZoneVisit
        billing_zone_names = {"billing"}

        sessions = (
            db.query(Session)
            .filter(Session.store_id == store_id, Session.is_staff == False)  # noqa: E712
            .all()
        )

        result = []
        for sess in sessions:
            # Find the latest billing zone exit time
            billing_exits = []
            for zv in sess.zone_visits:
                if zv.zone_name in billing_zone_names:
                    billing_exits.append(zv)

            if not billing_exits:
                continue

            latest_billing = max(billing_exits, key=lambda z: z.exit_time or z.entry_time or datetime.min)
            billing_exit_ts = latest_billing.exit_time or latest_billing.entry_time
            billing_dwell = sum(
                (zv.dwell_seconds or 0) for zv in billing_exits
            )

            # Use session identity_confidence from constituent events
            identity_conf = sess.session_confidence

            result.append({
                "session": sess,
                "billing_exit": billing_exit_ts,
                "billing_dwell": billing_dwell,
                "identity_confidence": identity_conf,
            })

        return result

    def _attribute_one(
        self,
        txn: Transaction,
        billing_sessions: List[Dict[str, Any]],
        db: DBSession,
    ) -> AttributionResult:
        """Attribute a single transaction to the best matching session."""
        best_match = None
        best_gap = float("inf")
        best_conf = 0.0

        for info in billing_sessions:
            billing_exit: Optional[datetime] = info["billing_exit"]
            if billing_exit is None:
                continue

            gap = (txn.timestamp - billing_exit).total_seconds()

            # Only consider sessions where billing zone exit preceded transaction
            # within the window
            if 0 <= gap <= self.billing_window_seconds:
                if gap < best_gap:
                    best_gap = gap
                    best_match = info
                    # Temporal proximity score: 1.0 at gap=0, 0.0 at window end
                    temporal_score = 1.0 - (gap / self.billing_window_seconds)
                    best_conf = (
                        temporal_score
                        * info["identity_confidence"]
                    )

        if best_match is None:
            return AttributionResult(
                transaction_id=txn.transaction_id,
                session_id=None,
                visitor_id=None,
                attributed=False,
                attribution_confidence=0.0,
                attribution_reason=(
                    f"No session found in billing zone within "
                    f"{self.billing_window_seconds}s of transaction {txn.transaction_id}"
                ),
            )

        sess: Session = best_match["session"]
        reason = (
            f"Visitor {sess.visitor_id[:8]} present in Billing Zone for "
            f"{best_match['billing_dwell']:.0f}s, transaction "
            f"{txn.transaction_id} occurred {best_gap:.0f}s after billing exit "
            f"(temporal_score={1 - best_gap/self.billing_window_seconds:.3f}, "
            f"identity_confidence={best_match['identity_confidence']:.3f})"
        )

        # Update transaction
        txn.attributed_visitor_id = sess.visitor_id
        txn.attributed_session_id = sess.session_id
        txn.attribution_confidence = round(best_conf, 4)
        txn.attribution_reason = reason
        txn.is_attributed = True

        # Update session
        sess.converted = True
        sess.transaction_id = txn.transaction_id
        sess.attribution_confidence = round(best_conf, 4)
        sess.attribution_reason = reason

        return AttributionResult(
            transaction_id=txn.transaction_id,
            session_id=sess.session_id,
            visitor_id=sess.visitor_id,
            attributed=True,
            attribution_confidence=round(best_conf, 4),
            attribution_reason=reason,
            temporal_gap_seconds=best_gap,
            billing_dwell_seconds=best_match["billing_dwell"],
        )

    # ── CSV parsing ───────────────────────────────────────────────────────────

    def _parse_csv(self, csv_path: str) -> List[Dict[str, str]]:
        """Parse CSV file into list of dicts.  Handles pandas and stdlib csv."""
        try:
            if _PANDAS_AVAILABLE:
                import pandas as pd  # noqa: PLC0415
                df = pd.read_csv(csv_path, dtype=str, on_bad_lines="warn")
                return df.fillna("").to_dict(orient="records")
            else:
                with open(csv_path, newline="", encoding="utf-8-sig") as f:
                    reader = _csv.DictReader(f)
                    return [dict(row) for row in reader]
        except Exception as exc:
            logger.error("CSV parse error for %s: %s", csv_path, exc)
            return []

    @staticmethod
    def _make_txn_id(row: Dict[str, str]) -> str:
        """Derive a stable transaction ID.

        Prefer invoice_number; fall back to order_id + product_id or UUID.
        Note: The CSV has multiple lines per order (one per product), so we
        combine invoice_number + SKU to get a truly unique row ID.
        """
        invoice = str(row.get("invoice_number", "")).strip()
        sku = str(row.get("sku", "")).strip() or str(row.get("product_id", "")).strip()
        if invoice:
            return f"{invoice}_{sku}" if sku else invoice
        order = str(row.get("order_id", "")).strip()
        if order:
            return f"{order}_{sku}" if sku else order
        return str(uuid.uuid4())

    @staticmethod
    def _parse_timestamp(row: Dict[str, str]) -> Optional[datetime]:
        """Parse order_date + order_time → datetime."""
        date_str = str(row.get("order_date", "")).strip()
        time_str = str(row.get("order_time", "")).strip()
        if not date_str:
            return None
        combined = f"{date_str} {time_str}".strip()
        formats = [
            "%d-%m-%Y %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%Y-%m-%dT%H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(combined, fmt)
            except ValueError:
                continue
        logger.warning("Cannot parse timestamp: '%s'", combined)
        return None

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(str(value).replace(",", "").strip())
        except (ValueError, TypeError):
            return default
