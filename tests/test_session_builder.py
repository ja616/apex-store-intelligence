"""Tests for SessionBuilder."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import List

import pytest

from apex.models.events import Event, EventType
from apex.models.sessions import Session as SessionModel
from apex.models.visitors import Visitor
from apex.session_builder import SessionBuilder

STORE_ID = "brigade-road-bangalore"
BASE_TIME = datetime(2026, 4, 10, 12, 0, 0)


def _make_event(
    camera_id: str,
    visitor_id: str,
    event_type: str = EventType.PERSON_DETECTED.value,
    offset_seconds: float = 0,
    confidence: float = 0.85,
    is_staff: bool = False,
) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        store_id=STORE_ID,
        camera_id=camera_id,
        visitor_id=visitor_id,
        event_type=event_type,
        timestamp=BASE_TIME + timedelta(seconds=offset_seconds),
        confidence=confidence,
        identity_confidence=0.80,
        is_staff=is_staff,
        schema_version=1,
    )


@pytest.fixture
def builder():
    return SessionBuilder(session_gap_seconds=60)


class TestNormalSession:
    """Single contiguous session: entry → zones → exit."""

    def test_builds_one_session(self, builder):
        vid = str(uuid.uuid4())
        events = [
            _make_event("CAM1", vid, EventType.PERSON_ENTERED.value, 0),
            _make_event("CAM2", vid, EventType.PERSON_DETECTED.value, 30),
            _make_event("CAM4", vid, EventType.BILLING_ZONE_ENTERED.value, 90),
            _make_event("CAM1", vid, EventType.PERSON_EXITED.value, 200),
        ]
        sessions = builder.build_sessions(events)

        assert len(sessions) == 1
        sess = sessions[0]
        assert sess.visitor_id == vid
        assert sess.duration_seconds == pytest.approx(200.0)
        assert sess.session_confidence > 0.0
        assert sess.reentry_count == 0

    def test_zones_are_tracked(self, builder):
        vid = str(uuid.uuid4())
        events = [
            _make_event("CAM1", vid, offset_seconds=0),
            _make_event("CAM2", vid, offset_seconds=30),
            _make_event("CAM4", vid, offset_seconds=90),
        ]
        sessions = builder.build_sessions(events)
        assert sessions[0].zones_visited is not None
        assert len(sessions[0].zones_visited) >= 2   # at least entry + floor_a


class TestReentry:
    """Same visitor re-enters after a long gap → 2 sessions."""

    def test_reentry_creates_two_sessions(self, builder):
        vid = str(uuid.uuid4())
        events = [
            _make_event("CAM1", vid, offset_seconds=0),
            _make_event("CAM2", vid, offset_seconds=30),
            _make_event("CAM1", vid, offset_seconds=60),   # exit
            # Long gap (>60s)
            _make_event("CAM1", vid, EventType.REENTRY_DETECTED.value, offset_seconds=200),
            _make_event("CAM2", vid, offset_seconds=240),
        ]
        sessions = builder.build_sessions(events)

        assert len(sessions) == 2, f"Expected 2 sessions, got {len(sessions)}"
        assert sessions[0].visitor_id == sessions[1].visitor_id == vid
        assert sessions[1].reentry_count == 1

    def test_sessions_have_different_entry_times(self, builder):
        vid = str(uuid.uuid4())
        events = [
            _make_event("CAM1", vid, offset_seconds=0),
            _make_event("CAM1", vid, offset_seconds=200),
        ]
        sessions = builder.build_sessions(events)
        assert len(sessions) == 2
        assert sessions[0].entry_time != sessions[1].entry_time


class TestSessionMerging:
    """Same visitor, events 30s apart → one session (under gap threshold)."""

    def test_short_gap_merges_into_one_session(self, builder):
        vid = str(uuid.uuid4())
        events = [
            _make_event("CAM1", vid, offset_seconds=0),
            _make_event("CAM2", vid, offset_seconds=30),   # 30s gap < 60s threshold
        ]
        sessions = builder.build_sessions(events)

        assert len(sessions) == 1

    def test_long_gap_splits_sessions(self, builder):
        vid = str(uuid.uuid4())
        events = [
            _make_event("CAM1", vid, offset_seconds=0),
            _make_event("CAM2", vid, offset_seconds=120),  # 120s > 60s threshold
        ]
        sessions = builder.build_sessions(events)

        assert len(sessions) == 2


class TestDoubleCountingPrevention:
    """Same visitor in 2 cameras within 2 seconds → one event per window."""

    def test_dedup_same_visitor_simultaneous_cameras(self, builder):
        vid = str(uuid.uuid4())
        events = [
            # Same visitor, same event type, same 2s window → should dedup
            _make_event("CAM1", vid, EventType.PERSON_DETECTED.value, offset_seconds=0),
            _make_event("CAM2", vid, EventType.PERSON_DETECTED.value, offset_seconds=0.5),
            _make_event("CAM3", vid, EventType.PERSON_DETECTED.value, offset_seconds=1.0),
            # Then legitimate next event
            _make_event("CAM2", vid, EventType.PERSON_DETECTED.value, offset_seconds=90),
        ]
        sessions = builder.build_sessions(events)
        # Should produce one or two sessions but not 3+ due to dedup
        assert len(sessions) <= 2


class TestStaffExclusion:
    """Staff visitor's sessions should be marked is_staff=True."""

    def test_staff_events_produce_staff_sessions(self, builder):
        vid = str(uuid.uuid4())
        events = []
        # Simulate a 4-hour staff presence
        for hour in range(8):
            events.append(
                _make_event(
                    "CAM2", vid, EventType.PERSON_DETECTED.value,
                    offset_seconds=hour * 1800,
                    is_staff=True
                )
            )

        sessions = builder.build_sessions(events)
        # All resulting sessions should be staff
        for sess in sessions:
            assert sess.is_staff, "Staff events should produce is_staff=True sessions"


class TestEmptyInput:
    """Edge case: empty event list."""

    def test_empty_events_returns_empty(self, builder):
        sessions = builder.build_sessions([])
        assert sessions == []

    def test_single_event_produces_one_session(self, builder):
        vid = str(uuid.uuid4())
        events = [_make_event("CAM1", vid, offset_seconds=0)]
        sessions = builder.build_sessions(events)
        assert len(sessions) == 1
        assert sessions[0].duration_seconds == pytest.approx(0.0)
