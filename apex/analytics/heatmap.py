"""Zone heatmap generator.

Returns per-zone traffic statistics normalised to a 0–100 scale.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session as DBSession

from apex.models.sessions import Session, ZoneVisit

logger = logging.getLogger(__name__)


@dataclass
class ZoneStats:
    zone_name: str
    visit_count: int = 0
    avg_dwell_seconds: float = 0.0
    total_dwell_seconds: float = 0.0
    traffic_density: float = 0.0   # normalised 0–100
    confidence: float = 0.0


@dataclass
class HeatmapData:
    store_id: str
    zones: Dict[str, ZoneStats] = field(default_factory=dict)
    metric_confidence: float = 0.0
    generated_at: Optional[datetime] = None


class HeatmapEngine:
    """Compute per-zone traffic heatmap from ZoneVisit data."""

    def get_heatmap(
        self,
        store_id: str,
        db: DBSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> HeatmapData:
        """Aggregate zone-level dwell statistics.

        Staff sessions are excluded via their parent Session.is_staff flag.
        Returns zone → ZoneStats mapping with traffic_density normalised 0–100.
        """
        # Query non-staff sessions for this store
        session_q = (
            db.query(Session.session_id)
            .filter(
                Session.store_id == store_id,
                Session.is_staff == False,  # noqa: E712
            )
        )
        if start_time:
            session_q = session_q.filter(Session.entry_time >= start_time)
        if end_time:
            session_q = session_q.filter(Session.entry_time <= end_time)

        session_ids = [r[0] for r in session_q.all()]

        if not session_ids:
            return HeatmapData(
                store_id=store_id,
                generated_at=datetime.utcnow(),
            )

        # Fetch all zone visits for those sessions
        zone_visits: List[ZoneVisit] = (
            db.query(ZoneVisit)
            .filter(ZoneVisit.session_id.in_(session_ids))
            .all()
        )

        # Aggregate per zone
        stats: Dict[str, ZoneStats] = {}
        for zv in zone_visits:
            zone = zv.zone_name or "unknown"
            if zone not in stats:
                stats[zone] = ZoneStats(zone_name=zone)
            s = stats[zone]
            s.visit_count += 1
            dwell = zv.dwell_seconds or 0.0
            s.total_dwell_seconds += dwell

        # Compute averages and per-zone confidence
        conf_sums: Dict[str, list] = {z: [] for z in stats}
        for zv in zone_visits:
            zone = zv.zone_name or "unknown"
            if zv.confidence > 0:
                conf_sums[zone].append(zv.confidence)

        for zone, s in stats.items():
            s.avg_dwell_seconds = (
                s.total_dwell_seconds / s.visit_count if s.visit_count > 0 else 0.0
            )
            confs = conf_sums.get(zone, [])
            s.confidence = round(sum(confs) / len(confs), 4) if confs else 0.5

        # Normalise traffic_density to 0–100
        if stats:
            max_visits = max(s.visit_count for s in stats.values())
            for s in stats.values():
                s.traffic_density = round(
                    s.visit_count / max_visits * 100, 2
                ) if max_visits > 0 else 0.0

        # Overall confidence
        all_confs = [s.confidence for s in stats.values()]
        overall_conf = round(sum(all_confs) / len(all_confs), 4) if all_confs else 0.0

        return HeatmapData(
            store_id=store_id,
            zones=stats,
            metric_confidence=overall_conf,
            generated_at=datetime.utcnow(),
        )
