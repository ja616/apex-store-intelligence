"""Tests for AnomalyEngine."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

from apex.analytics.anomaly import AnomalyEngine
from apex.models.events import Event, EventType
from apex.models.sessions import Session as SessionModel, ZoneVisit

STORE_ID = "brigade-road-bangalore"


def _make_session(
    db,
    visitor_id: str,
    entry_time: datetime,
    duration: float = 300,
    converted: bool = False,
    is_staff: bool = False,
    zones: list = None,
    confidence: float = 0.8,
) -> SessionModel:
    sess = SessionModel(
        session_id=str(uuid.uuid4()),
        visitor_id=visitor_id,
        store_id=STORE_ID,
        entry_time=entry_time,
        exit_time=entry_time + timedelta(seconds=duration),
        duration_seconds=duration,
        converted=converted,
        session_confidence=confidence,
        is_staff=is_staff,
        reentry_count=0,
        zones_visited=zones or ["entry"],
    )
    db.add(sess)
    db.flush()
    return sess


def _make_event(
    db,
    camera_id: str,
    visitor_id: str,
    ts: datetime,
    event_type: str = EventType.PERSON_DETECTED.value,
    is_staff: bool = False,
    identity_conf: float = 0.85,
) -> Event:
    ev = Event(
        event_id=str(uuid.uuid4()),
        store_id=STORE_ID,
        camera_id=camera_id,
        visitor_id=visitor_id,
        event_type=event_type,
        timestamp=ts,
        confidence=0.85,
        identity_confidence=identity_conf,
        is_staff=is_staff,
        schema_version=1,
    )
    db.add(ev)
    db.flush()
    return ev


# Store hours for test
STORE_OPEN = datetime(2026, 4, 10, 11, 0, 0)   # 11:00 (store hours 10–21)


@pytest.fixture
def engine():
    return AnomalyEngine(
        queue_threshold=3,           # lower for easier testing
        queue_duration_minutes=2.0,
        conversion_drop_threshold=0.30,
        dead_zone_minutes=5.0,       # short for testing
        stale_feed_minutes=5.0,      # short for testing
        abnormal_dwell_sigma=2.0,
    )


class TestQueueSpike:
    """QUEUE_SPIKE triggers when billing zone > threshold for > duration."""

    def test_queue_spike_detected(self, db_session, engine):
        ts = STORE_OPEN
        for i in range(5):   # 5 visitors > threshold of 3
            _make_event(db_session, "CAM4", str(uuid.uuid4()), ts + timedelta(seconds=i))
        db_session.commit()

        anomalies = engine.detect_all(
            STORE_ID, db_session,
            reference_time=ts + timedelta(minutes=3),
            billing_cameras=["CAM4", "CAM5"],
            all_cameras=["CAM1", "CAM2", "CAM3", "CAM4", "CAM5"],
        )

        queue_spikes = [a for a in anomalies if a.anomaly_type == "QUEUE_SPIKE"]
        assert len(queue_spikes) >= 1, "Expected at least one QUEUE_SPIKE anomaly"
        assert queue_spikes[0].severity == "HIGH"
        assert queue_spikes[0].confidence > 0.0

    def test_normal_queue_no_spike(self, db_session, engine):
        ts = STORE_OPEN
        # Only 2 visitors (below threshold of 3)
        for i in range(2):
            _make_event(db_session, "CAM4", str(uuid.uuid4()), ts + timedelta(seconds=i))
        db_session.commit()

        anomalies = engine.detect_all(
            STORE_ID, db_session,
            reference_time=ts + timedelta(minutes=3),
            billing_cameras=["CAM4", "CAM5"],
            all_cameras=["CAM1", "CAM2", "CAM3", "CAM4", "CAM5"],
        )
        queue_spikes = [a for a in anomalies if a.anomaly_type == "QUEUE_SPIKE"]
        assert len(queue_spikes) == 0


class TestStaleFeed:
    """STALE_FEED triggers when no events from a camera for > threshold."""

    def test_stale_feed_triggers(self, db_session, engine):
        # No events at all → all cameras stale
        db_session.commit()

        anomalies = engine.detect_all(
            STORE_ID, db_session,
            reference_time=STORE_OPEN + timedelta(minutes=10),
            billing_cameras=["CAM4", "CAM5"],
            all_cameras=["CAM1", "CAM2", "CAM3", "CAM4", "CAM5"],
        )
        stale = [a for a in anomalies if a.anomaly_type == "STALE_FEED"]
        assert len(stale) >= 1
        assert all(a.severity == "HIGH" for a in stale)

    def test_fresh_feed_no_stale(self, db_session, engine):
        now = STORE_OPEN + timedelta(minutes=10)
        cameras = ["CAM1", "CAM2", "CAM3", "CAM4", "CAM5"]
        for cam in cameras:
            _make_event(db_session, cam, str(uuid.uuid4()), now - timedelta(seconds=30))
        db_session.commit()

        anomalies = engine.detect_all(
            STORE_ID, db_session,
            reference_time=now,
            billing_cameras=["CAM4", "CAM5"],
            all_cameras=cameras,
        )
        stale = [a for a in anomalies if a.anomaly_type == "STALE_FEED"]
        assert len(stale) == 0


class TestConversionDrop:
    """CONVERSION_DROP triggers on > 30% drop vs 7-day average."""

    def test_conversion_drop_detected(self, db_session, engine):
        # Create 20 sessions over 7 days with 50% conversion (baseline)
        base_day = STORE_OPEN - timedelta(days=7)
        for i in range(20):
            _make_session(
                db_session,
                str(uuid.uuid4()),
                entry_time=base_day + timedelta(hours=i),
                converted=(i < 10),   # 50% conversion baseline
            )

        # Today: only 10% conversion (5 sessions, 1 converted) → 80% drop
        today = STORE_OPEN
        for i in range(10):
            _make_session(
                db_session,
                str(uuid.uuid4()),
                entry_time=today + timedelta(minutes=i * 10),
                converted=(i == 0),   # 1 out of 10 = 10% conversion
            )
        db_session.commit()

        anomalies = engine.detect_all(
            STORE_ID, db_session,
            reference_time=today + timedelta(hours=8),
        )
        drops = [a for a in anomalies if a.anomaly_type == "CONVERSION_DROP"]
        assert len(drops) >= 1
        assert drops[0].severity == "MEDIUM"


class TestAbnormalDwell:
    """ABNORMAL_DWELL triggers when dwell > N sigma from mean."""

    def test_abnormal_dwell_detected(self, db_session, engine):
        now = STORE_OPEN + timedelta(hours=2)
        # Normal sessions (mean ~300s)
        for _ in range(10):
            _make_session(db_session, str(uuid.uuid4()), entry_time=now, duration=300)

        # Outlier (3000s >> mean + 2σ)
        _make_session(db_session, str(uuid.uuid4()), entry_time=now, duration=3000)
        db_session.commit()

        anomalies = engine.detect_all(
            STORE_ID, db_session,
            reference_time=now + timedelta(minutes=5),
        )
        dwell_anomalies = [a for a in anomalies if a.anomaly_type == "ABNORMAL_DWELL"]
        assert len(dwell_anomalies) >= 1


class TestNoFalsePositivesOnNormalData:
    """Normal operational data should not trigger anomalies."""

    def test_no_anomalies_on_normal_data(self, db_session, engine):
        now = STORE_OPEN + timedelta(hours=2)
        cameras = ["CAM1", "CAM2", "CAM3", "CAM4", "CAM5"]

        # Fresh events from all cameras
        for cam in cameras:
            _make_event(db_session, cam, str(uuid.uuid4()), now - timedelta(seconds=10))

        # Normal sessions (1-2 people in billing, normal dwells)
        for i in range(5):
            _make_session(db_session, str(uuid.uuid4()), entry_time=now - timedelta(minutes=i * 5), duration=300)

        db_session.commit()

        anomalies = engine.detect_all(
            STORE_ID, db_session,
            reference_time=now,
            billing_cameras=["CAM4", "CAM5"],
            all_cameras=cameras,
        )

        # With fresh feeds and normal data, no queue spikes or stale feeds
        queue_spikes = [a for a in anomalies if a.anomaly_type == "QUEUE_SPIKE"]
        stale = [a for a in anomalies if a.anomaly_type == "STALE_FEED"]
        assert len(queue_spikes) == 0, "No queue spike expected on normal data"
        assert len(stale) == 0, "No stale feed expected when cameras are active"
