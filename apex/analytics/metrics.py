"""Store metrics calculator.

All metrics exclude staff (is_staff=True).
Confidence degrades when many low-confidence sessions exist.
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session as DBSession

from apex.models.sessions import Session

logger = logging.getLogger(__name__)


@dataclass
class StoreMetrics:
    """Aggregated store metrics for a given time window."""
    store_id: str
    unique_visitors: int = 0
    total_sessions: int = 0
    converted_sessions: int = 0
    conversion_rate: float = 0.0
    avg_dwell_seconds: float = 0.0
    median_dwell_seconds: float = 0.0
    peak_hour: Optional[int] = None
    peak_hour_count: int = 0
    total_revenue: float = 0.0
    metric_confidence: float = 0.0
    reasoning: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class MetricsEngine:
    """Compute store-level metrics from Session data."""

    def get_store_metrics(
        self,
        store_id: str,
        db: DBSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> StoreMetrics:
        """Compute all store metrics for the given window.

        Staff sessions are excluded.  Confidence degrades when many sessions
        have low individual confidence.
        """
        query = (
            db.query(Session)
            .filter(
                Session.store_id == store_id,
                Session.is_staff == False,  # noqa: E712
            )
        )

        if start_time:
            query = query.filter(Session.entry_time >= start_time)
        if end_time:
            query = query.filter(Session.entry_time <= end_time)

        sessions: List[Session] = query.all()

        metrics = StoreMetrics(store_id=store_id, start_time=start_time, end_time=end_time)

        if not sessions:
            metrics.reasoning = {
                "note": "No customer sessions found in the given time window",
                "staff_excluded": True,
            }
            metrics.metric_confidence = 0.0
            return metrics

        # ── Unique visitors ───────────────────────────────────────────────────
        unique_visitor_ids = {s.visitor_id for s in sessions}
        metrics.unique_visitors = len(unique_visitor_ids)
        metrics.total_sessions = len(sessions)

        # ── Conversion ───────────────────────────────────────────────────────
        converted = [s for s in sessions if s.converted]
        metrics.converted_sessions = len(converted)
        metrics.conversion_rate = (
            len(converted) / len(sessions) if sessions else 0.0
        )

        # ── Dwell time ────────────────────────────────────────────────────────
        dwells = [
            s.duration_seconds
            for s in sessions
            if s.duration_seconds is not None and s.duration_seconds >= 0
        ]
        if dwells:
            metrics.avg_dwell_seconds = sum(dwells) / len(dwells)
            sorted_dwells = sorted(dwells)
            n = len(sorted_dwells)
            if n % 2 == 0:
                metrics.median_dwell_seconds = (
                    sorted_dwells[n // 2 - 1] + sorted_dwells[n // 2]
                ) / 2
            else:
                metrics.median_dwell_seconds = sorted_dwells[n // 2]

        # ── Peak hour ─────────────────────────────────────────────────────────
        hour_counts: Counter = Counter()
        for s in sessions:
            if s.entry_time:
                hour_counts[s.entry_time.hour] += 1
        if hour_counts:
            peak_hour, peak_count = hour_counts.most_common(1)[0]
            metrics.peak_hour = peak_hour
            metrics.peak_hour_count = peak_count

        # ── Revenue ───────────────────────────────────────────────────────────
        from apex.models.transactions import Transaction  # avoid circular at module lvl
        txn_ids = [s.transaction_id for s in converted if s.transaction_id]
        if txn_ids:
            txns = (
                db.query(Transaction)
                .filter(Transaction.transaction_id.in_(txn_ids))
                .all()
            )
            metrics.total_revenue = sum(t.amount for t in txns)

        # ── Confidence ────────────────────────────────────────────────────────
        confidences = [s.session_confidence for s in sessions if s.session_confidence > 0]
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            # Penalty when many sessions are low-confidence
            low_conf_ratio = sum(1 for c in confidences if c < 0.5) / len(confidences)
            metrics.metric_confidence = round(avg_conf * (1.0 - 0.3 * low_conf_ratio), 4)
        else:
            metrics.metric_confidence = 0.5   # default when no confidence data

        # ── Reasoning ─────────────────────────────────────────────────────────
        metrics.reasoning = {
            "total_sessions": metrics.total_sessions,
            "unique_visitors": metrics.unique_visitors,
            "converted_sessions": metrics.converted_sessions,
            "conversion_rate_pct": round(metrics.conversion_rate * 100, 2),
            "avg_dwell_minutes": round(metrics.avg_dwell_seconds / 60, 2),
            "peak_hour": (
                f"{metrics.peak_hour:02d}:00–{metrics.peak_hour:02d}:59"
                if metrics.peak_hour is not None
                else "N/A"
            ),
            "peak_hour_visitor_count": metrics.peak_hour_count,
            "metric_confidence": metrics.metric_confidence,
            "confidence_note": (
                "Confidence reflects mean session identity confidence; "
                "low-confidence sessions degrade the score."
            ),
            "staff_excluded": True,
            "time_window": {
                "start": start_time.isoformat() if start_time else None,
                "end": end_time.isoformat() if end_time else None,
            },
        }

        return metrics

    def get_funnel(
        self,
        store_id: str,
        db: DBSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Compute entry→browse→billing→purchase funnel with confidence."""
        sessions: List[Session] = (
            db.query(Session)
            .filter(
                Session.store_id == store_id,
                Session.is_staff == False,  # noqa: E712
            )
            .all()
        )

        if start_time:
            sessions = [s for s in sessions if s.entry_time and s.entry_time >= start_time]
        if end_time:
            sessions = [s for s in sessions if s.entry_time and s.entry_time <= end_time]

        total_entered = len(sessions)

        browsed = [
            s for s in sessions
            if s.zones_visited and len(s.zones_visited) > 1
        ]

        billing = [
            s for s in sessions
            if s.zones_visited and any(
                z in ("billing",) for z in (s.zones_visited or [])
            )
        ]

        purchased = [s for s in sessions if s.converted]

        def _stage_conf(stage_sessions: List[Session]) -> float:
            confs = [s.session_confidence for s in stage_sessions if s.session_confidence > 0]
            return round(sum(confs) / len(confs), 4) if confs else 0.0

        def _drop_off(from_n: int, to_n: int) -> float:
            if from_n == 0:
                return 0.0
            return round((from_n - to_n) / from_n * 100, 2)

        return {
            "store_id": store_id,
            "stages": [
                {
                    "stage": "entered",
                    "count": total_entered,
                    "confidence": _stage_conf(sessions),
                    "drop_off_pct": 0.0,
                },
                {
                    "stage": "browsed",
                    "count": len(browsed),
                    "confidence": _stage_conf(browsed),
                    "drop_off_pct": _drop_off(total_entered, len(browsed)),
                },
                {
                    "stage": "billing_zone",
                    "count": len(billing),
                    "confidence": _stage_conf(billing),
                    "drop_off_pct": _drop_off(len(browsed), len(billing)),
                },
                {
                    "stage": "purchased",
                    "count": len(purchased),
                    "confidence": _stage_conf(purchased),
                    "drop_off_pct": _drop_off(len(billing), len(purchased)),
                },
            ],
            "overall_conversion_rate": round(
                len(purchased) / max(total_entered, 1) * 100, 2
            ),
            "metric_confidence": _stage_conf(sessions),
        }
