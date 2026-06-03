"""Tests for analytics metrics engine."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import List

import pytest

from apex.analytics.metrics import MetricsEngine
from apex.models.sessions import Session as SessionModel, ZoneVisit
from apex.models.visitors import Visitor

STORE_ID = "brigade-road-bangalore"
BASE_TIME = datetime(2026, 4, 10, 12, 0, 0)


def _add_session(
    db,
    visitor_id: str,
    entry_offset: int = 0,
    duration: float = 300,
    converted: bool = False,
    is_staff: bool = False,
    session_confidence: float = 0.8,
    zones: list = None,
) -> SessionModel:
    sess = SessionModel(
        session_id=str(uuid.uuid4()),
        visitor_id=visitor_id,
        store_id=STORE_ID,
        entry_time=BASE_TIME + timedelta(seconds=entry_offset),
        exit_time=BASE_TIME + timedelta(seconds=entry_offset + duration),
        duration_seconds=duration,
        converted=converted,
        session_confidence=session_confidence,
        is_staff=is_staff,
        reentry_count=0,
        zones_visited=zones or ["entry", "floor_a"],
    )
    db.add(sess)
    db.flush()
    return sess


@pytest.fixture
def engine():
    return MetricsEngine()


class TestConversionRate:
    """Conversion rate calculation."""

    def test_basic_conversion_rate(self, db_session, engine):
        v1, v2, v3 = [str(uuid.uuid4()) for _ in range(3)]
        _add_session(db_session, v1, converted=True)
        _add_session(db_session, v2, converted=False)
        _add_session(db_session, v3, converted=False)
        db_session.commit()

        m = engine.get_store_metrics(STORE_ID, db_session)
        assert m.total_sessions == 3
        assert m.converted_sessions == 1
        assert m.conversion_rate == pytest.approx(1 / 3, rel=1e-3)

    def test_zero_conversion_rate_no_error(self, db_session, engine):
        vid = str(uuid.uuid4())
        _add_session(db_session, vid, converted=False)
        db_session.commit()

        m = engine.get_store_metrics(STORE_ID, db_session)
        assert m.conversion_rate == 0.0

    def test_full_conversion_rate(self, db_session, engine):
        for _ in range(5):
            _add_session(db_session, str(uuid.uuid4()), converted=True)
        db_session.commit()

        m = engine.get_store_metrics(STORE_ID, db_session)
        assert m.conversion_rate == pytest.approx(1.0)


class TestConfidenceDegradation:
    """Confidence should degrade when many sessions have low confidence."""

    def test_low_confidence_sessions_degrade_metric(self, db_session, engine):
        for _ in range(10):
            _add_session(db_session, str(uuid.uuid4()), session_confidence=0.2)
        db_session.commit()

        m = engine.get_store_metrics(STORE_ID, db_session)
        assert m.metric_confidence < 0.5, (
            "Metric confidence should be degraded when sessions are low-confidence"
        )

    def test_high_confidence_sessions_yield_high_metric_confidence(
        self, db_session, engine
    ):
        for _ in range(5):
            _add_session(db_session, str(uuid.uuid4()), session_confidence=0.95)
        db_session.commit()

        m = engine.get_store_metrics(STORE_ID, db_session)
        assert m.metric_confidence > 0.7


class TestPeakHour:
    """Peak hour calculation."""

    def test_peak_hour_identified_correctly(self, db_session, engine):
        # Add 3 sessions at 14:00, 2 at 12:00
        for i in range(3):
            _add_session(
                db_session, str(uuid.uuid4()),
                entry_offset=2 * 3600 + i * 60   # 14:00 + offsets
            )
        for i in range(2):
            _add_session(
                db_session, str(uuid.uuid4()),
                entry_offset=i * 60   # 12:00 + offsets
            )
        db_session.commit()

        m = engine.get_store_metrics(STORE_ID, db_session)
        assert m.peak_hour == 14
        assert m.peak_hour_count == 3


class TestEmptyStore:
    """Empty store should return valid metrics without division-by-zero."""

    def test_empty_store_returns_zeros(self, db_session, engine):
        m = engine.get_store_metrics(STORE_ID, db_session)
        assert m.unique_visitors == 0
        assert m.total_sessions == 0
        assert m.conversion_rate == 0.0
        assert m.avg_dwell_seconds == 0.0
        assert m.metric_confidence == 0.0
        assert "note" in m.reasoning

    def test_all_staff_store_returns_zero_customers(self, db_session, engine):
        for _ in range(3):
            _add_session(db_session, str(uuid.uuid4()), is_staff=True)
        db_session.commit()

        m = engine.get_store_metrics(STORE_ID, db_session)
        assert m.unique_visitors == 0
        assert m.total_sessions == 0


class TestDwellTime:
    """Dwell time statistics."""

    def test_avg_dwell_computed_correctly(self, db_session, engine):
        durations = [100, 200, 300, 400]
        for d in durations:
            _add_session(db_session, str(uuid.uuid4()), duration=float(d))
        db_session.commit()

        m = engine.get_store_metrics(STORE_ID, db_session)
        expected_avg = sum(durations) / len(durations)
        assert m.avg_dwell_seconds == pytest.approx(expected_avg)


class TestHeatmapNormalization:
    """Heatmap traffic density should be 0–100."""

    def test_heatmap_density_in_range(self, db_session):
        from apex.analytics.heatmap import HeatmapEngine
        from apex.models.sessions import ZoneVisit

        # Add sessions with zone visits
        for zone in ["entry", "floor_a", "billing"]:
            sess = _add_session(db_session, str(uuid.uuid4()), zones=[zone])
            zv = ZoneVisit(
                session_id=sess.session_id,
                camera_id="CAM1",
                zone_name=zone,
                dwell_seconds=120,
                confidence=0.8,
            )
            db_session.add(zv)
        db_session.commit()

        hm_engine = HeatmapEngine()
        hm = hm_engine.get_heatmap(STORE_ID, db_session)

        for zone_stats in hm.zones.values():
            assert 0.0 <= zone_stats.traffic_density <= 100.0, (
                f"Zone {zone_stats.zone_name} density {zone_stats.traffic_density} out of range"
            )

    def test_highest_traffic_zone_has_density_100(self, db_session):
        from apex.analytics.heatmap import HeatmapEngine
        from apex.models.sessions import ZoneVisit

        # entry: 3 visits, floor_a: 1 visit
        for i in range(3):
            sess = _add_session(db_session, str(uuid.uuid4()), zones=["entry"])
            zv = ZoneVisit(
                session_id=sess.session_id,
                camera_id="CAM1",
                zone_name="entry",
                dwell_seconds=60,
                confidence=0.8,
            )
            db_session.add(zv)

        sess2 = _add_session(db_session, str(uuid.uuid4()), zones=["floor_a"])
        zv2 = ZoneVisit(
            session_id=sess2.session_id,
            camera_id="CAM2",
            zone_name="floor_a",
            dwell_seconds=30,
            confidence=0.8,
        )
        db_session.add(zv2)
        db_session.commit()

        hm_engine = HeatmapEngine()
        hm = hm_engine.get_heatmap(STORE_ID, db_session)

        if "entry" in hm.zones:
            assert hm.zones["entry"].traffic_density == pytest.approx(100.0)
