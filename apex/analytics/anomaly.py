"""Rule-based Anomaly Detection Engine.

Detects:
  QUEUE_SPIKE   — billing zone > 5 people for > 5 min           [HIGH]
  CONVERSION_DROP — conversion rate drops > 30% vs 7-day avg    [MEDIUM]
  DEAD_ZONE     — zone with 0 visits for > 30 min (store hours) [LOW]
  STALE_FEED    — no events from a camera for > 10 min          [HIGH]
  ABNORMAL_DWELL — visitor dwell > 3 sigma from mean            [LOW]

Every anomaly has: anomaly_id, type, severity, confidence, reason,
                   suggested_action, detection_rule, detected_at, camera_id.
"""
from __future__ import annotations

import logging
import math
import statistics
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session as DBSession

from apex.models.events import Event, EventType
from apex.models.sessions import Session, ZoneVisit

logger = logging.getLogger(__name__)

_STORE_OPEN_HOUR = 10
_STORE_CLOSE_HOUR = 21


@dataclass
class Anomaly:
    anomaly_id: str
    anomaly_type: str
    severity: str          # HIGH | MEDIUM | LOW
    confidence: float      # 0-1
    reason: str
    suggested_action: str
    detection_rule: str
    detected_at: datetime
    camera_id: Optional[str] = None
    zone_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AnomalyEngine:
    """Detect operational anomalies from the event and session data."""

    def __init__(
        self,
        queue_threshold: int = 5,
        queue_duration_minutes: float = 5.0,
        conversion_drop_threshold: float = 0.30,
        dead_zone_minutes: float = 30.0,
        stale_feed_minutes: float = 10.0,
        abnormal_dwell_sigma: float = 3.0,
        store_open_hour: int = _STORE_OPEN_HOUR,
        store_close_hour: int = _STORE_CLOSE_HOUR,
    ) -> None:
        self.queue_threshold = queue_threshold
        self.queue_duration_minutes = queue_duration_minutes
        self.conversion_drop_threshold = conversion_drop_threshold
        self.dead_zone_minutes = dead_zone_minutes
        self.stale_feed_minutes = stale_feed_minutes
        self.abnormal_dwell_sigma = abnormal_dwell_sigma
        self.store_open_hour = store_open_hour
        self.store_close_hour = store_close_hour

    def detect_all(
        self,
        store_id: str,
        db: DBSession,
        reference_time: Optional[datetime] = None,
        billing_cameras: Optional[List[str]] = None,
        all_cameras: Optional[List[str]] = None,
    ) -> List[Anomaly]:
        """Run all anomaly detectors and return found anomalies."""
        now = reference_time or datetime.utcnow()
        billing_cameras = billing_cameras or ["CAM4", "CAM5"]
        all_cameras = all_cameras or ["CAM1", "CAM2", "CAM3", "CAM4", "CAM5"]

        anomalies: List[Anomaly] = []
        anomalies.extend(self._detect_queue_spike(store_id, db, now, billing_cameras))
        anomalies.extend(self._detect_conversion_drop(store_id, db, now))
        anomalies.extend(self._detect_dead_zones(store_id, db, now))
        anomalies.extend(self._detect_stale_feed(store_id, db, now, all_cameras))
        anomalies.extend(self._detect_abnormal_dwell(store_id, db, now))
        return anomalies

    # ── QUEUE_SPIKE ───────────────────────────────────────────────────────────

    def _detect_queue_spike(
        self,
        store_id: str,
        db: DBSession,
        now: datetime,
        billing_cameras: List[str],
    ) -> List[Anomaly]:
        """Detect when billing zone has > queue_threshold people for > queue_duration_minutes."""
        window_start = now - timedelta(minutes=self.queue_duration_minutes * 2)

        events: List[Event] = (
            db.query(Event)
            .filter(
                Event.store_id == store_id,
                Event.camera_id.in_(billing_cameras),
                Event.is_staff == False,  # noqa: E712
                Event.timestamp >= window_start,
                Event.timestamp <= now,
            )
            .order_by(Event.timestamp)
            .all()
        )

        if not events:
            return []

        # Slide a window of queue_duration_minutes and count unique visitors
        threshold_delta = timedelta(minutes=self.queue_duration_minutes)
        spike_windows: list = []

        for i, ev in enumerate(events):
            window_end = ev.timestamp + threshold_delta
            in_window = {
                e.visitor_id for e in events
                if ev.timestamp <= e.timestamp <= window_end
                and e.visitor_id is not None
            }
            if len(in_window) > self.queue_threshold:
                spike_windows.append((ev.timestamp, len(in_window)))

        if not spike_windows:
            return []

        peak_ts, peak_count = max(spike_windows, key=lambda x: x[1])

        # Confidence from mean identity confidence of events in spike window
        confs = [e.identity_confidence for e in events if e.identity_confidence > 0]
        conf = round(sum(confs) / len(confs), 3) if confs else 0.7

        return [Anomaly(
            anomaly_id=str(uuid.uuid4()),
            anomaly_type="QUEUE_SPIKE",
            severity="HIGH",
            confidence=conf,
            reason=(
                f"Billing zone had {peak_count} simultaneous visitors at "
                f"{peak_ts.strftime('%H:%M')} — exceeds threshold of "
                f"{self.queue_threshold} for {self.queue_duration_minutes} min"
            ),
            suggested_action=(
                "Open additional billing counters or redirect customers to "
                "alternate checkout lanes to reduce queue length."
            ),
            detection_rule=(
                f"billing_zone_occupancy > {self.queue_threshold} for "
                f"> {self.queue_duration_minutes} min"
            ),
            detected_at=now,
            camera_id=billing_cameras[0] if billing_cameras else None,
            zone_name="billing",
            metadata={"peak_count": peak_count, "peak_time": peak_ts.isoformat()},
        )]

    # ── CONVERSION_DROP ───────────────────────────────────────────────────────

    def _detect_conversion_drop(
        self,
        store_id: str,
        db: DBSession,
        now: datetime,
    ) -> List[Anomaly]:
        """Detect > 30% drop in conversion rate vs rolling 7-day average."""
        # Today's conversion rate
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_sessions = self._get_customer_sessions(db, store_id, today_start, now)
        if len(today_sessions) < 5:
            return []   # not enough data for today

        today_rate = sum(1 for s in today_sessions if s.converted) / len(today_sessions)

        # 7-day baseline (exclude today)
        week_start = today_start - timedelta(days=7)
        baseline_sessions = self._get_customer_sessions(
            db, store_id, week_start, today_start
        )
        if len(baseline_sessions) < 10:
            return []   # insufficient baseline

        baseline_rate = (
            sum(1 for s in baseline_sessions if s.converted) / len(baseline_sessions)
        )

        if baseline_rate == 0:
            return []

        drop_pct = (baseline_rate - today_rate) / baseline_rate
        if drop_pct < self.conversion_drop_threshold:
            return []

        conf = round(min(drop_pct / 0.5, 1.0) * 0.8, 3)   # scales with severity

        return [Anomaly(
            anomaly_id=str(uuid.uuid4()),
            anomaly_type="CONVERSION_DROP",
            severity="MEDIUM",
            confidence=conf,
            reason=(
                f"Conversion rate today {today_rate:.1%} is {drop_pct:.1%} below "
                f"7-day baseline of {baseline_rate:.1%}"
            ),
            suggested_action=(
                "Investigate billing zone queue times, staff training, or "
                "product placement. Consider targeted promotions."
            ),
            detection_rule=(
                f"today_conversion_rate < (7day_avg × {1 - self.conversion_drop_threshold:.0%})"
            ),
            detected_at=now,
            metadata={
                "today_rate": round(today_rate, 4),
                "baseline_rate": round(baseline_rate, 4),
                "drop_pct": round(drop_pct, 4),
            },
        )]

    # ── DEAD_ZONE ─────────────────────────────────────────────────────────────

    def _detect_dead_zones(
        self,
        store_id: str,
        db: DBSession,
        now: datetime,
    ) -> List[Anomaly]:
        """Detect zones with zero activity for > dead_zone_minutes during store hours."""
        if not self._is_store_hours(now):
            return []

        window_start = now - timedelta(minutes=self.dead_zone_minutes)

        # All zone visits in the window
        active_zones: set = set()
        sessions_in_window = self._get_customer_sessions(db, store_id, window_start, now)
        for sess in sessions_in_window:
            for zv in sess.zone_visits:
                if zv.zone_name:
                    active_zones.add(zv.zone_name)

        # Determine all expected zones
        from apex.pipeline.topology import CameraTopologyService  # avoid circular
        try:
            topo = CameraTopologyService()
            all_zones = {topo.get_zone(c) for c in topo.all_cameras()}
        except Exception:
            all_zones = {"entry", "floor_a", "floor_b", "billing"}

        dead_zones = all_zones - active_zones - {"billing"}  # billing silence handled differently
        anomalies = []
        for zone in dead_zones:
            anomalies.append(Anomaly(
                anomaly_id=str(uuid.uuid4()),
                anomaly_type="DEAD_ZONE",
                severity="LOW",
                confidence=0.75,
                reason=(
                    f"Zone '{zone}' has had zero visitor activity for "
                    f">{self.dead_zone_minutes:.0f} minutes during store hours"
                ),
                suggested_action=(
                    f"Check if zone '{zone}' camera is functioning. "
                    "Consider repositioning products or adding signage."
                ),
                detection_rule=(
                    f"zone_visits == 0 for > {self.dead_zone_minutes} min during store hours"
                ),
                detected_at=now,
                zone_name=zone,
                metadata={"inactive_minutes": self.dead_zone_minutes},
            ))
        return anomalies

    # ── STALE_FEED ────────────────────────────────────────────────────────────

    def _detect_stale_feed(
        self,
        store_id: str,
        db: DBSession,
        now: datetime,
        all_cameras: List[str],
    ) -> List[Anomaly]:
        """Detect cameras with no events for > stale_feed_minutes during store hours."""
        if not self._is_store_hours(now):
            return []

        threshold_ts = now - timedelta(minutes=self.stale_feed_minutes)
        anomalies = []

        for camera_id in all_cameras:
            latest_event: Optional[Event] = (
                db.query(Event)
                .filter(
                    Event.store_id == store_id,
                    Event.camera_id == camera_id,
                    Event.timestamp <= now,
                )
                .order_by(Event.timestamp.desc())
                .first()
            )

            is_stale = (
                latest_event is None
                or latest_event.timestamp < threshold_ts
            )
            if is_stale:
                gap_min = (
                    (now - latest_event.timestamp).total_seconds() / 60
                    if latest_event else self.stale_feed_minutes + 1
                )
                anomalies.append(Anomaly(
                    anomaly_id=str(uuid.uuid4()),
                    anomaly_type="STALE_FEED",
                    severity="HIGH",
                    confidence=0.95,
                    reason=(
                        f"Camera {camera_id} has sent no events for "
                        f"{gap_min:.0f} minutes — feed may be down"
                    ),
                    suggested_action=(
                        f"Check camera {camera_id} connection, power, and "
                        "network status. Restart if necessary."
                    ),
                    detection_rule=(
                        f"no_events_from_camera for > {self.stale_feed_minutes} min "
                        "during store hours"
                    ),
                    detected_at=now,
                    camera_id=camera_id,
                    metadata={
                        "last_event_ts": (
                            latest_event.timestamp.isoformat()
                            if latest_event
                            else None
                        ),
                        "gap_minutes": round(gap_min, 2),
                    },
                ))

        return anomalies

    # ── ABNORMAL_DWELL ────────────────────────────────────────────────────────

    def _detect_abnormal_dwell(
        self,
        store_id: str,
        db: DBSession,
        now: datetime,
    ) -> List[Anomaly]:
        """Detect visitors with dwell time > N sigma from mean."""
        sessions: List[Session] = (
            db.query(Session)
            .filter(
                Session.store_id == store_id,
                Session.is_staff == False,  # noqa: E712
                Session.duration_seconds.isnot(None),
            )
            .all()
        )

        dwells = [s.duration_seconds for s in sessions if s.duration_seconds and s.duration_seconds > 0]
        if len(dwells) < 5:
            return []

        mean_d = statistics.mean(dwells)
        stdev_d = statistics.stdev(dwells)
        if stdev_d == 0:
            return []

        threshold = mean_d + self.abnormal_dwell_sigma * stdev_d
        anomalies = []

        for sess in sessions:
            if sess.duration_seconds and sess.duration_seconds > threshold:
                z_score = (sess.duration_seconds - mean_d) / stdev_d
                conf = round(min(z_score / (self.abnormal_dwell_sigma * 2), 1.0) * 0.8, 3)
                anomalies.append(Anomaly(
                    anomaly_id=str(uuid.uuid4()),
                    anomaly_type="ABNORMAL_DWELL",
                    severity="LOW",
                    confidence=conf,
                    reason=(
                        f"Visitor {sess.visitor_id[:8]} dwell "
                        f"{sess.duration_seconds/60:.1f} min is "
                        f"{z_score:.1f}σ above mean ({mean_d/60:.1f} min)"
                    ),
                    suggested_action=(
                        "Consider checking if visitor needs assistance or "
                        "if there is unusual loitering near high-value items."
                    ),
                    detection_rule=(
                        f"session_duration > mean + {self.abnormal_dwell_sigma}σ"
                    ),
                    detected_at=now,
                    metadata={
                        "visitor_id": sess.visitor_id,
                        "dwell_seconds": sess.duration_seconds,
                        "mean_seconds": round(mean_d, 1),
                        "z_score": round(z_score, 2),
                    },
                ))

        return anomalies

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _is_store_hours(self, now: datetime) -> bool:
        return self.store_open_hour <= now.hour < self.store_close_hour

    def _get_customer_sessions(
        self,
        db: DBSession,
        store_id: str,
        start: datetime,
        end: datetime,
    ) -> List[Session]:
        return (
            db.query(Session)
            .filter(
                Session.store_id == store_id,
                Session.is_staff == False,  # noqa: E712
                Session.entry_time >= start,
                Session.entry_time <= end,
            )
            .all()
        )
