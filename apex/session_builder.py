"""Session Builder — converts raw events into structured visitor sessions.

Rules:
 - New session if gap > session_gap_seconds between consecutive events
 - Re-entry: same visitor, new session after gap > session_gap_seconds
 - Merge overlapping tracklets from same camera if identity_confidence > 0.8
 - Dedup: same visitor in 2 cameras within 2 seconds → one event
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from apex.config import settings
from apex.models.events import Event, EventType
from apex.models.sessions import Session, ZoneVisit
from apex.models.visitors import Visitor
from apex.pipeline.staff_classifier import StaffClassifier
from apex.pipeline.topology import CameraTopologyService

logger = logging.getLogger(__name__)

_DEDUP_WINDOW_SECONDS = 2.0    # same visitor in 2 cams within this → one event
_MERGE_CONFIDENCE = 0.80       # tracklet merge threshold


class SessionBuilder:
    """Build sessions from a list of Event ORM objects."""

    def __init__(
        self,
        session_gap_seconds: int | None = None,
        billing_cameras: List[str] | None = None,
        topology: Optional[CameraTopologyService] = None,
        staff_classifier: Optional[StaffClassifier] = None,
    ) -> None:
        self.session_gap_seconds = session_gap_seconds or settings.session_gap_seconds
        self.billing_cameras = set(
            billing_cameras or settings.billing_zone_cameras
        )
        self.topology = topology or CameraTopologyService()
        self.staff_classifier = staff_classifier or StaffClassifier()

    # ── Public API ────────────────────────────────────────────────────────────

    def build_sessions(
        self,
        events: List[Event],
        visitors: Optional[Dict[str, Visitor]] = None,
    ) -> List[Session]:
        """Convert a flat list of events into structured sessions.

        Args:
            events:   All events for one store, pre-sorted by timestamp.
            visitors: Optional pre-loaded visitor map (visitor_id → Visitor).

        Returns:
            List of Session objects (not yet persisted to DB).
        """
        if not events:
            return []

        # Sort by timestamp
        events = sorted(events, key=lambda e: e.timestamp)

        # De-duplicate simultaneous multi-camera events
        events = self._dedup_events(events)

        # Group by visitor_id
        by_visitor: Dict[str, List[Event]] = defaultdict(list)
        for ev in events:
            if ev.visitor_id:
                by_visitor[ev.visitor_id].append(ev)

        sessions: List[Session] = []
        for visitor_id, visitor_events in by_visitor.items():
            visitor_events.sort(key=lambda e: e.timestamp)
            is_staff = self._is_staff(visitor_events, visitors, visitor_id)
            visitor_sessions = self._split_into_sessions(
                visitor_id, visitor_events, is_staff
            )
            sessions.extend(visitor_sessions)

        return sessions

    # ── Deduplication ─────────────────────────────────────────────────────────

    def _dedup_events(self, events: List[Event]) -> List[Event]:
        """Remove duplicate multi-camera events for the same visitor within window."""
        seen: Dict[Tuple[str, str], datetime] = {}  # (visitor_id, window_bucket) → ts
        result: List[Event] = []

        for ev in events:
            if not ev.visitor_id:
                result.append(ev)
                continue

            # Bucket into 2-second windows
            ts = ev.timestamp
            bucket_key = (
                ev.visitor_id,
                ev.event_type,
                str(int(ts.timestamp() // _DEDUP_WINDOW_SECONDS)),
            )
            if bucket_key in seen:
                # Keep highest confidence
                prev_ts = seen[bucket_key]
                # If duplicate, skip this one (retain first)
                continue

            seen[bucket_key] = ts
            result.append(ev)

        return result

    # ── Session splitting ─────────────────────────────────────────────────────

    def _split_into_sessions(
        self,
        visitor_id: str,
        events: List[Event],
        is_staff: bool,
    ) -> List[Session]:
        """Split events into sessions based on temporal gap."""
        if not events:
            return []

        sessions: List[Session] = []
        current_events: List[Event] = [events[0]]
        reentry_count = 0

        for ev in events[1:]:
            prev_ts = current_events[-1].timestamp
            gap = (ev.timestamp - prev_ts).total_seconds()

            if gap > self.session_gap_seconds and ev.event_type != EventType.PERSON_EXITED.value:
                # Flush current session, start new one
                sess = self._build_one_session(
                    visitor_id, current_events, is_staff, reentry_count
                )
                sessions.append(sess)
                reentry_count += 1
                current_events = [ev]
            else:
                current_events.append(ev)

        # Flush last batch
        if current_events:
            sess = self._build_one_session(
                visitor_id, current_events, is_staff, reentry_count
            )
            sessions.append(sess)

        return sessions

    def _build_one_session(
        self,
        visitor_id: str,
        events: List[Event],
        is_staff: bool,
        reentry_count: int,
    ) -> Session:
        """Construct a single Session from a contiguous event list."""
        entry_time = events[0].timestamp
        exit_time = events[-1].timestamp
        duration = (exit_time - entry_time).total_seconds()

        # Zone journey
        zones = self._extract_zones(events)

        # Session confidence = weighted mean of event confidences
        confidences = [e.confidence for e in events if e.confidence > 0]
        session_conf = float(sum(confidences) / len(confidences)) if confidences else 0.5

        session_id = str(uuid.uuid4())

        # Build ZoneVisit children
        zone_visits = self._build_zone_visits(session_id, events)

        # Store_id from first event
        store_id = events[0].store_id if events else ""

        session = Session(
            session_id=session_id,
            visitor_id=visitor_id,
            store_id=store_id,
            entry_time=entry_time,
            exit_time=exit_time,
            duration_seconds=duration,
            converted=False,
            attribution_confidence=0.0,
            zones_visited=zones,
            session_confidence=session_conf,
            reentry_count=reentry_count,
            is_staff=is_staff,
        )
        session.zone_visits = zone_visits
        return session

    # ── Zone helpers ──────────────────────────────────────────────────────────

    def _extract_zones(self, events: List[Event]) -> List[str]:
        """Return ordered unique zone names visited."""
        zones: List[str] = []
        last_zone: Optional[str] = None
        for ev in events:
            zone = self.topology.get_zone(ev.camera_id)
            if zone != last_zone:
                zones.append(zone)
                last_zone = zone
        return zones

    def _build_zone_visits(
        self, session_id: str, events: List[Event]
    ) -> List[ZoneVisit]:
        """Build ZoneVisit objects for contiguous camera segments."""
        visits: List[ZoneVisit] = []
        if not events:
            return visits

        current_cam = events[0].camera_id
        current_zone = self.topology.get_zone(current_cam)
        segment_start = events[0].timestamp
        segment_events = [events[0]]

        def flush(end_ts: datetime) -> None:
            dwell = (end_ts - segment_start).total_seconds()
            confs = [e.confidence for e in segment_events if e.confidence > 0]
            conf = float(sum(confs) / len(confs)) if confs else 0.5
            visits.append(ZoneVisit(
                session_id=session_id,
                camera_id=current_cam,
                zone_name=current_zone,
                entry_time=segment_start,
                exit_time=end_ts,
                dwell_seconds=max(dwell, 0.0),
                confidence=conf,
            ))

        for ev in events[1:]:
            if ev.camera_id != current_cam:
                flush(ev.timestamp)
                current_cam = ev.camera_id
                current_zone = self.topology.get_zone(current_cam)
                segment_start = ev.timestamp
                segment_events = [ev]
            else:
                segment_events.append(ev)

        flush(events[-1].timestamp)
        return visits

    # ── Staff detection ───────────────────────────────────────────────────────

    def _is_staff(
        self,
        events: List[Event],
        visitors: Optional[Dict[str, Visitor]],
        visitor_id: str,
    ) -> bool:
        """Check staff status from visitor DB row first, then classifier."""
        # If any event is explicitly marked as staff, then they are staff
        if any(getattr(e, "is_staff", False) for e in events):
            return True

        if visitors and visitor_id in visitors:
            v = visitors[visitor_id]
            if v.staff_confidence >= 0.55:
                return v.is_staff

        # Use classifier on events as a fallback
        result = self.staff_classifier.classify(events)
        return result.is_staff
